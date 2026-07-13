from __future__ import annotations
import importlib.metadata
import numpy as np
import pytest
import hftbacktest as hbt
N=1_000_000_000
B=hbt.EXCH_EVENT|hbt.LOCAL_EVENT|hbt.BUY_EVENT
S=hbt.EXCH_EVENT|hbt.LOCAL_EVENT|hbt.SELL_EVENT

def e(ts,k,px,qty,ival):
 r=np.zeros(1,dtype=hbt.event_dtype)[0]; r['ev']=k; r['exch_ts']=ts; r['local_ts']=ts; r['px']=px; r['qty']=qty; r['ival']=ival; return r

def events(side,trade,cross):
 rows=[e(N,B|hbt.DEPTH_EVENT,100,10,-1),e(N,S|hbt.DEPTH_EVENT,100.5,10,1)]
 if trade:
  if side=='buy': rows += [e(3*N,S|hbt.TRADE_EVENT,100,15,-1),e(3*N+1,B|hbt.DEPTH_EVENT,100,0,-1),e(3*N+2,B|hbt.DEPTH_EVENT,99.5,8,-1)]
  else: rows += [e(3*N,B|hbt.TRADE_EVENT,100.5,15,1),e(3*N+1,S|hbt.DEPTH_EVENT,100.5,0,1),e(3*N+2,S|hbt.DEPTH_EVENT,101,8,1)]
 if cross: rows.append(e(5*N,(S if side=='buy' else B)|hbt.DEPTH_EVENT,100 if side=='buy' else 100.5,20,1 if side=='buy' else -1))
 rows.append(e(8*N,B|hbt.DEPTH_EVENT,99.5,9,-1)); out=np.zeros(len(rows),dtype=hbt.event_dtype)
 for i,r in enumerate(rows): out[i]=r
 return out

def run(side,qty,trade,cross):
 assert importlib.metadata.version('hftbacktest')=='2.4.4+carrybot.partialfill1'
 a=(hbt.BacktestAsset().add_data(events(side,trade,cross)).linear_asset(1).constant_order_latency(1_000_000,1_000_000).power_prob_queue_model(2).partial_fill_exchange().trading_value_fee_model(.001,.002).tick_size(.5).lot_size(1))
 x=hbt.HashMapMarketDepthBacktest([a])
 try:
  x.elapse(N+1)
  (x.submit_buy_order if side=='buy' else x.submit_sell_order)(0,1,100 if side=='buy' else 100.5,qty,hbt.GTC,hbt.LIMIT,False)
  x.wait_order_response(0,1,2*N); x.elapse(9*N); o=x.orders(0).get(1); s=x.state_values(0)
  return int(o.status),float(o.exec_qty),float(o.leaves_qty),float(x.position(0)),float(s.fee),int(s.num_trades),float(s.trading_volume)
 finally: x.close()

@pytest.mark.parametrize('side,pos',[('buy',5),('sell',-5)])
def test_partial_only(side,pos):
 st,ex,le,p,fee,n,vol=run(side,20,True,False); px=100 if side=='buy' else 100.5
 assert (st,ex,le,p,n,vol)==(5,5,15,pos,1,5); assert fee==pytest.approx(5*px*.001)

@pytest.mark.parametrize('side,pos',[('buy',20),('sell',-20)])
def test_partial_then_final(side,pos):
 st,ex,le,p,fee,n,vol=run(side,20,True,True); px=100 if side=='buy' else 100.5
 assert (st,ex,le,p,n,vol)==(3,15,0,pos,2,20); assert fee==pytest.approx(20*px*.001)

@pytest.mark.parametrize('side,pos',[('buy',5),('sell',-5)])
def test_full_fill_control(side,pos):
 st,ex,le,p,fee,n,vol=run(side,5,True,False); assert (st,ex,le,p,n)==(3,5,0,pos,1)
