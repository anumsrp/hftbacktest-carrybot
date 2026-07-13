from __future__ import annotations

import importlib.metadata
import numpy as np
import pytest
import hftbacktest as hbt

N = 1_000_000_000
EXCH_LOCAL_BUY = hbt.EXCH_EVENT | hbt.LOCAL_EVENT | hbt.BUY_EVENT
EXCH_LOCAL_SELL = hbt.EXCH_EVENT | hbt.LOCAL_EVENT | hbt.SELL_EVENT


def _event(ts: int, kind: int, px: float, qty: float, ival: int):
    row = np.zeros(1, dtype=hbt.event_dtype)[0]
    row["ev"], row["exch_ts"], row["local_ts"] = kind, ts, ts
    row["px"], row["qty"], row["ival"] = px, qty, ival
    return row


def _events(*, side: str, with_trade: bool, with_cross: bool):
    rows = [
        _event(N, EXCH_LOCAL_BUY | hbt.DEPTH_EVENT, 100.0, 10.0, -1),
        _event(N, EXCH_LOCAL_SELL | hbt.DEPTH_EVENT, 100.5, 10.0, 1),
    ]
    if with_trade:
        if side == "buy":
            rows += [
                _event(3 * N, EXCH_LOCAL_SELL | hbt.TRADE_EVENT, 100.0, 15.0, -1),
                _event(3 * N + 1, EXCH_LOCAL_BUY | hbt.DEPTH_EVENT, 100.0, 0.0, -1),
                _event(3 * N + 2, EXCH_LOCAL_BUY | hbt.DEPTH_EVENT, 99.5, 8.0, -1),
            ]
        else:
            rows += [
                _event(3 * N, EXCH_LOCAL_BUY | hbt.TRADE_EVENT, 100.5, 15.0, 1),
                _event(3 * N + 1, EXCH_LOCAL_SELL | hbt.DEPTH_EVENT, 100.5, 0.0, 1),
                _event(3 * N + 2, EXCH_LOCAL_SELL | hbt.DEPTH_EVENT, 101.0, 8.0, 1),
            ]
    if with_cross:
        rows.append(_event(5 * N, (EXCH_LOCAL_SELL if side == "buy" else EXCH_LOCAL_BUY) | hbt.DEPTH_EVENT, 100.0 if side == "buy" else 100.5, 20.0, 1 if side == "buy" else -1))
    rows.append(_event(8 * N, EXCH_LOCAL_BUY | hbt.DEPTH_EVENT, 99.5, 9.0, -1))
    out = np.zeros(len(rows), dtype=hbt.event_dtype)
    for idx, row in enumerate(rows):
        out[idx] = row
    return out


def _run(*, side: str, qty: float, with_trade: bool, with_cross: bool):
    assert importlib.metadata.version("hftbacktest") == "2.4.4+carrybot.partialfill1"
    asset = (
        hbt.BacktestAsset()
        .add_data(_events(side=side, with_trade=with_trade, with_cross=with_cross))
        .linear_asset(1.0)
        .constant_order_latency(1_000_000, 1_000_000)
        .power_prob_queue_model(2)
        .partial_fill_exchange()
        .trading_value_fee_model(0.001, 0.002)
        .tick_size(0.5)
        .lot_size(1.0)
    )
    engine = hbt.HashMapMarketDepthBacktest([asset])
    order_id = 1
    try:
        engine.elapse(N + 1)
        if side == "buy":
            engine.submit_buy_order(0, order_id, 100.0, qty, hbt.GTC, hbt.LIMIT, False)
        else:
            engine.submit_sell_order(0, order_id, 100.5, qty, hbt.GTC, hbt.LIMIT, False)
        engine.wait_order_response(0, order_id, 2 * N)
        engine.elapse(9 * N)
        order = engine.orders(0).get(order_id)
        state = engine.state_values(0)
        return {
            "status": int(order.status),
            "exec_qty": float(order.exec_qty),
            "leaves_qty": float(order.leaves_qty),
            "position": float(engine.position(0)),
            "fee": float(state.fee),
            "num_trades": int(state.num_trades),
            "volume": float(state.trading_volume),
        }
    finally:
        engine.close()


@pytest.mark.parametrize("side,expected", [("buy", 5.0), ("sell", -5.0)])
def test_partial_fill_only_updates_accounting(side, expected):
    r = _run(side=side, qty=20.0, with_trade=True, with_cross=False)
    assert (r["status"], r["exec_qty"], r["leaves_qty"], r["position"], r["num_trades"]) == (5, 5.0, 15.0, expected, 1)
    px = 100.0 if side == "buy" else 100.5
    assert r["fee"] == pytest.approx(5.0 * px * 0.001)
    assert r["volume"] == pytest.approx(5.0)


@pytest.mark.parametrize("side,expected", [("buy", 20.0), ("sell", -20.0)])
def test_partial_then_final_accumulates_each_execution_once(side, expected):
    r = _run(side=side, qty=20.0, with_trade=True, with_cross=True)
    assert (r["status"], r["exec_qty"], r["leaves_qty"], r["position"], r["num_trades"]) == (3, 15.0, 0.0, expected, 2)
    px = 100.0 if side == "buy" else 100.5
    assert r["fee"] == pytest.approx(20.0 * px * 0.001)
    assert r["volume"] == pytest.approx(20.0)


@pytest.mark.parametrize("side,expected", [("buy", 5.0), ("sell", -5.0)])
def test_full_fill_control_is_unchanged(side, expected):
    r = _run(side=side, qty=5.0, with_trade=True, with_cross=False)
    assert (r["status"], r["exec_qty"], r["leaves_qty"], r["position"], r["num_trades"]) == (3, 5.0, 0.0, expected, 1)


def test_l3_builder_is_explicitly_not_applicable():
    asset = (
        hbt.BacktestAsset()
        .add_data(_events(side="buy", with_trade=True, with_cross=False))
        .linear_asset(1.0)
        .constant_order_latency(1_000_000, 1_000_000)
        .l3_fifo_queue_model()
        .partial_fill_exchange()
        .trading_value_fee_model(0.001, 0.002)
        .tick_size(0.5)
        .lot_size(1.0)
    )
    with pytest.raises(ValueError, match="L3PartialFillExchange is unsupported"):
        hbt.HashMapMarketDepthBacktest([asset])
