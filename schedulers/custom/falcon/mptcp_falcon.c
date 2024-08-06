/* MPTCP Scheduler module selector. Highly inspired by tcp_cong.c */
//Modified mptcp_blest to use selected subflow from userspace that was derived using FALCON framework

#include <linux/module.h>
#include <net/mptcp.h>
#include <trace/events/tcp.h>

static unsigned char num_segments __read_mostly = 1;
module_param(num_segments, byte, 0644); //makes sure the module variable num_segments is changeable via sysctl or with socket option 46.
MODULE_PARM_DESC(num_segments, "The number of consecutive segments that are part of a burst");


struct fsched_priv {
	//u32 last_rbuf_opti;
	// this has to be in the same format as the mptcp_sched_info struct defined in tcp.h to use setsockopt properly
	unsigned char quota;
	unsigned char num_segments;
};

struct rbuf_opti{
	u32 last_rbuf_opti;
};

static inline struct fsched_priv *fsched_get_priv(const struct tcp_sock *tp)
{
	return (struct fsched_priv *)&tp->mptcp->mptcp_sched[0];
}

static inline struct rbuf_opti *fsched_get_rbuf(const struct tcp_sock *tp)
{
	return (struct rbuf_opti *)&tp->mptcp->mptcp_sched[0];
}


/* If the sub-socket sk available to send the skb? */
static bool mptcp_f_is_available(const struct sock *sk, const struct sk_buff *skb,
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

/* Are we not allowed to reinject this skb on tp? */
static int mptcp_dont_reinject_skb(const struct tcp_sock *tp, const struct sk_buff *skb)
{
	/* If the skb has already been enqueued in this sk, try to find
	 * another one.
	 */
	return skb &&
		/* Has the skb already been enqueued into this subsocket? */
		mptcp_pi_to_flag(tp->mptcp->path_index) & TCP_SKB_CB(skb)->path_mask;
}


 /* Try to use the subflow chosen in userspace with setting msp->num_segments=1 if available and use other if not*/
struct sock *f_get_available_subflow(struct sock *meta_sk, struct sk_buff *skb,
				   bool zero_wnd_test)
{
	struct mptcp_cb *mpcb = tcp_sk(meta_sk)->mpcb;
	struct sock *sk = NULL, *bestsk = NULL, *backupsk = NULL;
	struct mptcp_tcp_sock *mptcp;
	
	/* Answer data_fin on same subflow!!! */
	if (meta_sk->sk_shutdown & RCV_SHUTDOWN &&
	    skb && mptcp_is_data_fin(skb)) {
		

		mptcp_for_each_sub(mpcb, mptcp) {
			sk = mptcp_to_sock(mptcp);
			
			
			if (tcp_sk(sk)->mptcp->path_index == mpcb->dfin_path_index &&
			   mptcp_is_available(sk, skb, zero_wnd_test))
				return sk;
		}
	}
	
	mptcp_for_each_sub(mpcb, mptcp) {
		struct tcp_sock *tp;
		struct fsched_priv *fsp;
		
		sk = mptcp_to_sock(mptcp);
		tp = tcp_sk(sk);
		fsp = fsched_get_priv(tp);
		
		
		if (!mptcp_f_is_available(sk,skb,zero_wnd_test,true)){ //only if available
			continue;
		}
		if (mptcp_dont_reinject_skb(tp, skb))
			continue;
			
		if(fsp->num_segments==0){ //only use the falcon selected subflow but give option of using other subflow if available
			backupsk = sk;
			continue;
		}
		
		bestsk = sk;
	}
	//always reset path mask similiar to round robin
	if (bestsk) {
		sk = bestsk;
	} else if(backupsk) {
		if(skb)
			TCP_SKB_CB(skb)->path_mask = 0;
		sk = backupsk;
	}else
		sk = NULL;
	if(sk!=NULL)
		pr_info("%d",sk->__sk_common.skc_daddr);

	return sk;
}

static struct sk_buff *mptcp_f_rcv_buf_optimization(struct sock *sk, int penal)
{
	struct sock *meta_sk;
	const struct tcp_sock *tp = tcp_sk(sk);
	struct mptcp_tcp_sock *mptcp;
	struct sk_buff *skb_head;
	struct rbuf_opti *rb = fsched_get_rbuf(tp);

	meta_sk = mptcp_meta_sk(sk);
	skb_head = tcp_rtx_queue_head(meta_sk);

	if (!skb_head)
		return NULL;

	/* If penalization is optional (coming from mptcp_next_segment() and
	 * We are not send-buffer-limited we do not penalize. The retransmission
	 * is just an optimization to fix the idle-time due to the delay before
	 * we wake up the application.
	 */
	if (!penal && sk_stream_memory_free(meta_sk))
		goto retrans;

	/* Only penalize again after an RTT has elapsed */
	if (tcp_jiffies32 - rb->last_rbuf_opti < usecs_to_jiffies(tp->srtt_us >> 3))
		//goto retrans;

	/* Half the cwnd of the slow flows */
	mptcp_for_each_sub(tp->mpcb, mptcp) {
		struct tcp_sock *tp_it = mptcp->tp;

		if (tp_it != tp &&
		    TCP_SKB_CB(skb_head)->path_mask & mptcp_pi_to_flag(tp_it->mptcp->path_index)) {
			if (tp->srtt_us < tp_it->srtt_us && inet_csk((struct sock *)tp_it)->icsk_ca_state == TCP_CA_Open) {
				u32 prior_cwnd = tp_it->snd_cwnd;

				tp_it->snd_cwnd = max(tp_it->snd_cwnd >> 1U, 1U);

				/* If in slow start, do not reduce the ssthresh */
				if (prior_cwnd >= tp_it->snd_ssthresh)
					tp_it->snd_ssthresh = max(tp_it->snd_ssthresh >> 1U, 2U);

				rb->last_rbuf_opti = tcp_jiffies32;
			}
		}
	}

retrans:

	/* Segment not yet injected into this path? Take it!!! */
	if (!(TCP_SKB_CB(skb_head)->path_mask & mptcp_pi_to_flag(tp->mptcp->path_index))) {
		bool do_retrans = false;
		mptcp_for_each_sub(tp->mpcb, mptcp) {
			struct tcp_sock *tp_it = mptcp->tp;

			if (tp_it != tp &&
			    TCP_SKB_CB(skb_head)->path_mask & mptcp_pi_to_flag(tp_it->mptcp->path_index)) {
				if (tp_it->snd_cwnd <= 4) {
					do_retrans = true;
					break;
				}

				if (4 * tp->srtt_us >= tp_it->srtt_us) {
					do_retrans = false;
					break;
				} else {
					do_retrans = true;
				}
			}
		}

		if (do_retrans && mptcp_is_available(sk, skb_head, false)) {
			trace_mptcp_retransmit(sk, skb_head);
			return skb_head;
		}
	}
	return NULL;
}

/* Returns the next segment to be sent from the mptcp meta-queue.
 * (chooses the reinject queue if any segment is waiting in it, otherwise,
 * chooses the normal write queue).
 * Sets *@reinject to 1 if the returned segment comes from the
 * reinject queue. Sets it to 0 if it is the regular send-head of the meta-sk,
 * and sets it to -1 if it is a meta-level retransmission to optimize the
 * receive-buffer.
 */
static struct sk_buff *__mptcp_f_next_segment(struct sock *meta_sk, int *reinject)
{
	const struct mptcp_cb *mpcb = tcp_sk(meta_sk)->mpcb;
	struct sk_buff *skb = NULL;

	*reinject = 0;

	/* If we are in fallback-mode, just take from the meta-send-queue */
	if (mpcb->infinite_mapping_snd || mpcb->send_infinite_mapping)
		return tcp_send_head(meta_sk);

	skb = skb_peek(&mpcb->reinject_queue);

	if (skb) {
		*reinject = 1;
	} else {
		skb = tcp_send_head(meta_sk);

		if (!skb && meta_sk->sk_socket &&
		    test_bit(SOCK_NOSPACE, &meta_sk->sk_socket->flags) &&
		    sk_stream_wspace(meta_sk) < sk_stream_min_wspace(meta_sk)) {
			struct sock *subsk = f_get_available_subflow(meta_sk, NULL,
									 false);
			if (!subsk)
				return NULL;

			skb = mptcp_f_rcv_buf_optimization(subsk, 0);
			if (skb)
				*reinject = -1;
		}
	}
	return skb;
}
// next segment function copied from mptcp_blest
static struct sk_buff *mptcp_f_next_segment(struct sock *meta_sk,
					  int *reinject,
					  struct sock **subsk,
					  unsigned int *limit)
{
	struct sk_buff *skb = __mptcp_f_next_segment(meta_sk, reinject);
	unsigned int mss_now;
	struct tcp_sock *subtp;
	u16 gso_max_segs;
	u32 max_len, max_segs, window, needed;

	/* As we set it, we have to reset it as well. */
	*limit = 0;

	if (!skb)
		return NULL;

	*subsk = f_get_available_subflow(meta_sk, skb, false);
	if (!*subsk)
		return NULL;

	subtp = tcp_sk(*subsk);
	mss_now = tcp_current_mss(*subsk);

	if (!*reinject && unlikely(!tcp_snd_wnd_test(tcp_sk(meta_sk), skb, mss_now))) {
		skb = mptcp_f_rcv_buf_optimization(*subsk, 1);
		if (skb)
			*reinject = -1;
		else
			return NULL;
	}
	
	/* No splitting required, as we will only send one single segment */
	if (skb->len <= mss_now)
		return skb;

	gso_max_segs = (*subsk)->sk_gso_max_segs;
	if (!gso_max_segs) // No gso supported on the subflow's NIC
		gso_max_segs = 1;
	
	//remove tcp_cwnd_test and only have gso
	max_segs = min_t(unsigned int, tcp_cwnd_test(subtp, skb), gso_max_segs);
	if (!max_segs)
		return NULL;

	// if there is room for a segment, schedule up to a complete TSO
	 //segment to avoid TSO splitting. Even if it is more than allowed by
	 // the congestion window.
	 
	max_len = gso_max_segs * mss_now; //* max_segs;
	window = tcp_wnd_end(subtp) - subtp->write_seq;

	needed = min(skb->len, window);
	//*limit = max_len;
	if (max_len <= skb->len)
		// Take max_win, which is actually the cwnd/gso-size 
		*limit = max_len;
	else
		// Or, take the window 
		*limit = needed;
	
	return skb;
}

static void fsched_init(struct sock *sk)
{
	struct fsched_priv *priv = fsched_get_priv(tcp_sk(sk));
	struct rbuf_opti * rb = fsched_get_rbuf(tcp_sk(sk));
	// default option is setting both paths to 1 which essentially means sending over the first available path with space
	priv->num_segments = num_segments;
	rb->last_rbuf_opti = tcp_jiffies32;
}

struct mptcp_sched_ops mptcp_sched_falcon = {
	.get_subflow = f_get_available_subflow,
	.next_segment = mptcp_f_next_segment,
	.init = fsched_init,
	.name = "falcon",
	.owner = THIS_MODULE,
};

static int __init f_register(void)
{
	BUILD_BUG_ON(sizeof(struct fsched_priv) > MPTCP_SCHED_SIZE);
	BUILD_BUG_ON(sizeof(struct rbuf_opti) > MPTCP_SCHED_SIZE);
	
	printk(KERN_INFO " falcon scheduler is loaded\n");

	if (mptcp_register_scheduler(&mptcp_sched_falcon))
		return -1;

	return 0;
}

static void f_unregister(void)
{
	mptcp_unregister_scheduler(&mptcp_sched_falcon);
}

module_init(f_register);
module_exit(f_unregister);

MODULE_AUTHOR("ME");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Falcon scheduler for mptcp, based on blest");
MODULE_VERSION("0.95");
