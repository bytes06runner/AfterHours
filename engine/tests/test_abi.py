"""Tests for cast-style signature parsing and encoding."""

from __future__ import annotations

from eth_abi import encode

from afterhours.chain.abi import (
    address_topic,
    decode_output,
    encode_call,
    parse_event,
    parse_function,
)


def test_parse_function_with_outputs() -> None:
    sig = parse_function("latestRoundData()(uint80,int256,uint256,uint256,uint80)")
    assert sig.canonical == "latestRoundData()"
    assert sig.outputs == ["uint80", "int256", "uint256", "uint256", "uint80"]
    assert sig.selector.hex() == "feaf968c"


def test_parse_function_with_tuple_input() -> None:
    sig = parse_function(
        "quoteExactInputSingle((address,address,uint256,uint24,uint160))(uint256,uint160,uint32,uint256)"
    )
    assert sig.inputs == ["(address,address,uint256,uint24,uint160)"]
    assert len(sig.outputs) == 4


def test_encode_matches_known_selector() -> None:
    data = encode_call("balanceOf(address)(uint256)", "0x" + "11" * 20)
    assert data[:4].hex() == "70a08231"
    assert len(data) == 36


def test_decode_single_and_multiple() -> None:
    assert decode_output("decimals()(uint8)", encode(["uint8"], [8])) == 8
    assert decode_output("f()(uint8,bool)", encode(["uint8", "bool"], [1, True])) == (1, True)


def test_event_topic_and_params() -> None:
    ev = parse_event(
        "AnswerUpdated(int256 indexed current,uint256 indexed roundId,uint256 updatedAt)"
    )
    assert ev.canonical == "AnswerUpdated(int256,uint256,uint256)"
    # keccak256("AnswerUpdated(int256,uint256,uint256)") from Chainlink's AggregatorInterface.
    assert ev.topic0.startswith(
        "0x0559884fd3a460db3073b7fc896cc77986f16e378210ded43186175bf646fc5f"
    )
    assert [p[2] for p in ev.params] == [True, True, False]


def test_address_topic() -> None:
    assert address_topic("0x" + "ab" * 20) == "0x" + "0" * 24 + "ab" * 20
