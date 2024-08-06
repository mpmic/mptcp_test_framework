/* MPTCP Scheduler module selector. Highly inspired by tcp_cong.c */

#include <linux/module.h>
#include <net/mptcp.h>

static unsigned char num_segments __read_mostly = 1;
module_param(num_segments, byte, 0644); //makes sure the module variable num_segments is changeable via sysctl or with socket option 46.
MODULE_PARM_DESC(num_segments, "The number of consecutive segments that are part of a burst");

static bool cwnd_limited __read_mostly = 1;
module_param(cwnd_limited, bool, 0644);
MODULE_PARM_DESC(cwnd_limited, "if set to 1, the scheduler tries to fill the congestion-window on all subflows");

struct mysched_priv{
  unsigned char quota;
  /* The number of consecutive segments that are part of a burst */
  unsigned char num_segments;
};

static struct mysched_priv *mysched_get_priv(const struct tcp_sock *tp)
{
	return (struct mysched_priv *)&tp->mptcp->mptcp_sched[0];
}

/* Heavily inspired by mptcp_rr and gaogogo/Experiment mysched.c
 */

/* If the sub-socket sk available to send the skb?*/
static bool mptcp_reles_is_available(const struct sock *sk, const struct sk_buff *skb,
				  bool zero_wnd_test, bool cwnd_test)
{
	const struct tcp_sock *tp = tcp_sk(sk);
	unsigned int space, in_flight;

	/* Set of states for which we are allowed to send data */
	if (!mptcp_sk_can_send(sk))
		return false;

	/* We do not send data on this subflow unless it is
	 * fully established, i.e. the 4th ack has been received.
	 */
	if (tp->mptcp->pre_established)
		return false;

	if (tp->pf)
		return false;

	if (inet_csk(sk)->icsk_ca_state == TCP_CA_Loss) {
		/* If SACK is disabled, and we got a loss, TCP does not exit
		 * the loss-state until something above high_seq has been acked.
		 * (see tcp_try_undo_recovery)
		 *
		 * high_seq is the snd_nxt at the moment of the RTO. As soon
		 * as we have an RTO, we won't push data on the subflow.
		 * Thus, snd_una can never go beyond high_seq.
		 */
		if (!tcp_is_reno(tp))
			return false;
		else if (tp->snd_una != tp->high_seq)
			return false;
	}

	if (!tp->mptcp->fully_established) {
		/* Make sure that we send in-order data */
		if (skb && tp->mptcp->second_packet &&
		    tp->mptcp->last_end_data_seq != TCP_SKB_CB(skb)->seq)
			return false;
	}

	if (!cwnd_test)
		goto zero_wnd_test;

	in_flight = tcp_packets_in_flight(tp);
	/* Not even a single spot in the cwnd */
	if (in_flight >= tp->snd_cwnd)
		return false;

	/* Now, check if what is queued in the subflow's send-queue
	 * already fills the cwnd.
	 */
	space = (tp->snd_cwnd - in_flight) * tp->mss_cache;

	if (tp->write_seq - tp->snd_nxt > space)
		return false;

zero_wnd_test:
	if (zero_wnd_test && !before(tp->write_seq, tcp_wnd_end(tp)))
		return false;

	return true;
}

/* Are we not allowed to reinject this skb on tp? Copied from default mptcp_sched.c*/
static int mptcp_reles_dont_reinject_skb(const struct tcp_sock *tp, const struct sk_buff *skb)
{
	/* If the skb has already been enqueued in this sk, try to find
	 * another one.
	 */
	return skb &&
		/* Has the skb already been enqueued into this subsocket? */
		mptcp_pi_to_flag(tp->mptcp->path_index) & TCP_SKB_CB(skb)->path_mask;
}

/* We just look for any subflow that is available */
static struct sock *reles_get_available_subflow(struct sock *meta_sk,
					     struct sk_buff *skb,
					     bool zero_wnd_test)
{
	const struct mptcp_cb *mpcb = tcp_sk(meta_sk)->mpcb;
	struct sock *sk = NULL, *bestsk = NULL, *backupsk = NULL;
	struct mptcp_tcp_sock *mptcp;
	unsigned int current_space = 0;
	
	/* Answer data_fin on same subflow!!! */
	if (meta_sk->sk_shutdown & RCV_SHUTDOWN &&
	    skb && mptcp_is_data_fin(skb)) {
		mptcp_for_each_sub(mpcb, mptcp) {
			sk = mptcp_to_sock(mptcp);
			if (tcp_sk(sk)->mptcp->path_index == mpcb->dfin_path_index &&
			    mptcp_reles_is_available(sk, skb, zero_wnd_test, true))
				return sk;
		}
	}
	mptcp_for_each_sub(mpcb, mptcp) {
		struct tcp_sock *tp;
		struct mysched_priv *msp;
		
		sk = mptcp_to_sock(mptcp);
		tp = tcp_sk(sk);
		msp = mysched_get_priv(tp);
		
		current_space = msp->num_segments - msp->quota;
		
		//if num_segments == 0 we dont want to use the subflow at all even if it is available
		if(msp->num_segments ==0){
			continue;
		}
		
		if (!mptcp_reles_is_available(sk, skb, zero_wnd_test, true)){
			continue;
		}
		
		if (mptcp_reles_dont_reinject_skb(tp, skb)) {
			backupsk = sk;
			continue;
		}

		bestsk = sk;
		
	}

	if (bestsk) {
		sk = bestsk;
	} else if (backupsk) {
		// It has been sent on all subflows once - let's give it a
		 // chance again by restarting its pathmask.
		if (skb)
			TCP_SKB_CB(skb)->path_mask = 0;
		sk = backupsk;
	}
	return sk;
}

/* Returns the next segment to be sent from the mptcp meta-queue.
 * (chooses the reinject queue if any segment is waiting in it, otherwise,
 * chooses the normal write queue).
 * Sets *@reinject to 1 if the returned segment comes from the
 * reinject queue. Sets it to 0 if it is the regular send-head of the meta-sk,
 * and sets it to -1 if it is a meta-level retransmission to optimize the
 * receive-buffer.
 */
static struct sk_buff *__mptcp_reles_next_segment(const struct sock *meta_sk, int *reinject)
{
	const struct mptcp_cb *mpcb = tcp_sk(meta_sk)->mpcb;
	struct sk_buff *skb = NULL;

	*reinject = 0;

	/* If we are in fallback-mode, just take from the meta-send-queue */
	if (mpcb->infinite_mapping_snd || mpcb->send_infinite_mapping)
		return tcp_send_head(meta_sk);

	skb = skb_peek(&mpcb->reinject_queue);

	if (skb)
		*reinject = 1;
	else
		skb = tcp_send_head(meta_sk);
	return skb;
}

static struct sk_buff *mptcp_reles_next_segment(struct sock *meta_sk,
					     int *reinject,
					     struct sock **subsk,
					     unsigned int *limit)
{
	const struct mptcp_cb *mpcb = tcp_sk(meta_sk)->mpcb;
	struct mptcp_tcp_sock *mptcp;
	struct sock *choose_sk = NULL;
	struct sk_buff *skb = __mptcp_reles_next_segment(meta_sk, reinject);
	unsigned char split = 1,max_space=0;    //difference to rr!
	unsigned char iter = 0, full_subs = 0;

	/* As we set it, we have to reset it as well. */
	*limit = 0;

	if (!skb)
		return NULL;

	if (*reinject) {
		*subsk = reles_get_available_subflow(meta_sk, skb, false);
		if (!*subsk)
			return NULL;

		return skb;
	}

retry:
  choose_sk = NULL;
  split = 0;
  iter = 0; 
  full_subs = 0; 
	/* First, we look for a subflow who is currently being used */
	mptcp_for_each_sub(mpcb, mptcp) {
	        
		struct sock *sk_it = mptcp_to_sock(mptcp);
		struct tcp_sock *tp_it = tcp_sk(sk_it);
		struct mysched_priv *msp = mysched_get_priv(tp_it);
		
		if (!mptcp_reles_is_available(sk_it, skb, false, cwnd_limited))
			continue;
		//skip subfows with num_segments = 0	
		if(msp->num_segments == 0){
			continue;
		}	

		iter++;
		
		
		/* Is this subflow currently being used? */
		if ((msp->quota >= 0) && (msp->quota < msp->num_segments) &&
      (msp->num_segments - msp->quota > split)) {
			split = msp->num_segments - msp->quota;
			if(max_space < split){
				choose_sk = sk_it; 
				max_space = split;
			}
		}
		
		/* Or, it must then be fully used  */
		if (msp->quota >= msp->num_segments)
			full_subs++;
	}

  if (choose_sk != NULL) //changed so that we now only go to found if we actually found a subflow
    goto found;
	/* All considered subflows have a full quota, and we considered at
	 * least one.
	 * For ReLes only reset if quota of both paths is filled ?
	 */
	if (iter && (iter == full_subs)) {
		/* So, we restart this round by setting quota to 0 and retry
		 * to find a subflow.
		 */
		mptcp_for_each_sub(mpcb, mptcp) {
			struct sock *sk_it = mptcp_to_sock(mptcp);
			struct tcp_sock *tp_it = tcp_sk(sk_it);
			struct mysched_priv *msp = mysched_get_priv(tp_it);

			if (!mptcp_reles_is_available(sk_it, skb, false, cwnd_limited))
				continue;
			msp->quota = 0;
			
		}

		goto retry;
	}

found:
	if (choose_sk) {
		unsigned int mss_now;
		struct tcp_sock *choose_tp = tcp_sk(choose_sk);
		struct mysched_priv *msp = mysched_get_priv(choose_tp);

		if (!mptcp_reles_is_available(choose_sk, skb, false, true))
			return NULL;
			
		if(choose_sk!=NULL)
			pr_info("%d",choose_sk->__sk_common.skc_daddr);		
		
		*subsk = choose_sk;
		mss_now = tcp_current_mss(*subsk);
		*limit = split * mss_now;

		if (skb->len > mss_now)
			msp->quota += DIV_ROUND_UP(skb->len, mss_now);
		else
			msp->quota++;

		return skb;
	}

	return NULL;
}


static void relessched_init(struct sock *sk)
{
  struct mysched_priv* priv = mysched_get_priv(tcp_sk(sk));
  priv->num_segments = num_segments;
}

static struct mptcp_sched_ops mptcp_sched_reles = {
	.get_subflow = reles_get_available_subflow,
	.next_segment = mptcp_reles_next_segment,
  	.init = relessched_init,
	.name = "reles",
	.owner = THIS_MODULE,
};
 
static int __init reles_register(void)
{
	BUILD_BUG_ON(sizeof(struct mysched_priv) > MPTCP_SCHED_SIZE);
	
	printk(KERN_INFO "relessched_priv is loaded\n");

	if (mptcp_register_scheduler(&mptcp_sched_reles))
		return -1;

	return 0;
}

static void reles_unregister(void)
{
	mptcp_unregister_scheduler(&mptcp_sched_reles);
}

module_init(reles_register);
module_exit(reles_unregister);

MODULE_AUTHOR("ME");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("reles demo scheduler for mptcp");
MODULE_VERSION("0.90");


