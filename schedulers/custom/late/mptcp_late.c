#include <linux/module.h>
#include <net/mptcp.h>


struct latesched_priv {
    u32 n;
    bool master;
};

struct latesched_cb {
    u32 round_time_end;
    u32 master_rtt;
};

static struct latesched_priv *late_get_priv(const struct tcp_sock *tp)
{
	return (struct latesched_priv *)&tp->mptcp->mptcp_sched[0];
}

static struct latesched_cb *late_get_cb(const struct tcp_sock *tp)
{
	return (struct latesched_cb *)&tp->mpcb->mptcp_sched[0];
}

static u32 loss_rate_1000(u32 lost_packets, u32 sent_packets)
{
    if (sent_packets <= 0)
        return 0;

    return (lost_packets * 1000) / sent_packets;
}

static u32 late_n(u32 cwnd, u32 loss_rate_1000)
{
    if (loss_rate_1000 > 1000)
        return 0;

    return (cwnd * (1000 - loss_rate_1000)) / 1000;
}

static void late_init_round(struct sock *meta_sk)
{
    struct latesched_priv *late_p;
    struct latesched_cb *late_cb = late_get_cb(tcp_sk(meta_sk));
    struct mptcp_cb *mpcb = tcp_sk(meta_sk)->mpcb;
    struct mptcp_tcp_sock *mptcp;

    struct tcp_sock* subflow_highest_rtt = NULL;
    u32 highest_rtt = 0;

    /* find master subflow (highest rtt) */
    mptcp_for_each_sub(mpcb, mptcp) {
        struct sock *subflow_sk = mptcp_to_sock(mptcp);
        struct tcp_sock *subflow_tp = tcp_sk(subflow_sk);
        late_p = late_get_priv(subflow_tp);

        if (subflow_tp->srtt_us > highest_rtt) {
            highest_rtt = subflow_tp->srtt_us;
            subflow_highest_rtt = subflow_tp;
        }

        late_p->master = false;
    }

    struct latesched_priv *highest_p = late_get_priv(subflow_highest_rtt);
    highest_p->master = true;

    late_cb->round_time_end = tcp_jiffies32 + (usecs_to_jiffies(highest_rtt >> 3) / 2);
    late_cb->master_rtt = highest_rtt;

    /* initialize per subflow values */
    mptcp_for_each_sub(mpcb, mptcp) {
        struct sock *subflow_sk = mptcp_to_sock(mptcp);
        struct tcp_sock *subflow_tp = tcp_sk(subflow_sk);
        late_p = late_get_priv(subflow_tp);

        u32 loss = loss_rate_1000(subflow_tp->lost, subflow_tp->data_segs_out);

        late_p->n = (late_p->master) ? subflow_tp->snd_cwnd : late_n(subflow_tp->snd_cwnd, loss);
    }
}

struct sock *late_get_subflow(struct sock *meta_sk, struct sk_buff *skb, bool zero_wnd_test)
{
    struct mptcp_cb *mpcb = tcp_sk(meta_sk)->mpcb;
    struct sock *bestsk = NULL;
    struct mptcp_tcp_sock *mptcp;

    struct latesched_priv *late_p;
    struct latesched_cb *late_cb = late_get_cb(tcp_sk(meta_sk));

    u32 lowest_rtt = UINT_MAX;

    /* answer data_fin on same subflow */
    if (meta_sk->sk_shutdown & RCV_SHUTDOWN && skb && mptcp_is_data_fin(skb)) {
        mptcp_for_each_sub(mpcb, mptcp) {
            bestsk = mptcp_to_sock(mptcp);

            if (tcp_sk(bestsk)->mptcp->path_index == mpcb->dfin_path_index &&
                mptcp_is_available(bestsk, skb, zero_wnd_test))
                return bestsk;
        }
    }

    /* find the lowest rtt subflow that still has sending space */
    mptcp_for_each_sub(mpcb, mptcp) {
        struct sock *subflow_sk = mptcp_to_sock(mptcp);
        struct tcp_sock *subflow_tp = tcp_sk(subflow_sk);
        late_p = late_get_priv(subflow_tp);

        /* if there is still time left in the round, recalculate n */
        if (late_p->n <= 0 && !late_p->master && late_cb->round_time_end > tcp_jiffies32) {
            u32 loss = loss_rate_1000(subflow_tp->lost, subflow_tp->data_segs_out);
            late_p->n = late_n(subflow_tp->snd_cwnd, loss);
        }

        /* skip subflows that have no sending space left */
        if (!mptcp_sk_can_send(subflow_sk) || late_p->n <= 0)
            continue;

        if (subflow_tp->srtt_us < lowest_rtt) {
            lowest_rtt = subflow_tp->srtt_us;
            bestsk = subflow_sk;
        }
    }

    /* if no sk found (i.e. no sending space left on master), start new round */
    if (!bestsk) {
        late_init_round(meta_sk);
    }

    if (!bestsk || !mptcp_is_available(bestsk, skb, zero_wnd_test)) {
        return NULL;
    }

    late_p = late_get_priv(tcp_sk(bestsk));
    late_p->n--;

    return bestsk;
}

static void late_init(struct sock *sk)
{
	struct latesched_priv *late_p = late_get_priv(tcp_sk(sk));
	struct latesched_cb *late_cb = late_get_cb(tcp_sk(mptcp_meta_sk(sk)));

    late_p->n = 0;
    late_p->master = false;

    late_cb->round_time_end = 0;
    late_cb->master_rtt = 0;
}

static struct mptcp_sched_ops mptcp_sched_late = {
	.get_subflow = late_get_subflow,
	.next_segment = mptcp_next_segment,
	.init = late_init,
	.name = "late",
	.owner = THIS_MODULE,
};

static int __init late_register(void)
{
	BUILD_BUG_ON(sizeof(struct latesched_priv) > MPTCP_SCHED_SIZE);
	BUILD_BUG_ON(sizeof(struct latesched_cb) > MPTCP_SCHED_DATA_SIZE);

	if (mptcp_register_scheduler(&mptcp_sched_late))
		return -1;

	return 0;
}

static void late_unregister(void)
{
	mptcp_unregister_scheduler(&mptcp_sched_late);
}

module_init(late_register);
module_exit(late_unregister);

MODULE_AUTHOR("Jonas");
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("LATE scheduler for MPTCP");
MODULE_VERSION("0.96");
