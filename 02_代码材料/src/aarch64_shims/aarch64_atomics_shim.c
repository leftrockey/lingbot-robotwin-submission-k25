/* Provides libgcc's outline-atomic helpers (__aarch64_*_sync) that SAPIEN's nightly aarch64 libsapien.so
 * imports dynamically but no shared libgcc exports. Built with -mno-outline-atomics so the builtins inline
 * to LSE/LL-SC instructions instead of calling back into these functions. */
#include <stdint.h>
#define SEQ __ATOMIC_SEQ_CST
#define CAS(N,T) T __aarch64_cas##N##_sync(T e, T d, T *p){ __atomic_compare_exchange_n(p,&e,d,0,SEQ,SEQ); return e; }
#define OP(name,N,T,expr) T __aarch64_##name##N##_sync(T v, T *p){ return expr; }
CAS(4,uint32_t) CAS(8,uint64_t)
OP(ldadd,4,uint32_t,__atomic_fetch_add(p,v,SEQ)) OP(ldadd,8,uint64_t,__atomic_fetch_add(p,v,SEQ))
OP(ldclr,4,uint32_t,__atomic_fetch_and(p,~v,SEQ)) OP(ldclr,8,uint64_t,__atomic_fetch_and(p,~v,SEQ))
OP(ldset,4,uint32_t,__atomic_fetch_or(p,v,SEQ))  OP(ldset,8,uint64_t,__atomic_fetch_or(p,v,SEQ))
OP(swp,4,uint32_t,__atomic_exchange_n(p,v,SEQ))  OP(swp,8,uint64_t,__atomic_exchange_n(p,v,SEQ))
