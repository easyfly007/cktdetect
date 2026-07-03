import json
from pathlib import Path

from cktdetect.cli import main

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def test_cli_report(tmp_path):
    out = tmp_path / "report.json"
    assert main([str(BENCH / "five_t_ota.sp"), "-o", str(out)]) == 0
    report = json.loads(out.read_text())

    assert report["flat"]["device_count"] == 11
    assert report["flat"]["devices_by_type"]["nmos"] == 4
    assert report["flat"]["devices_by_type"]["pmos"] == 2
    assert "ota5" in report["subckts"]
    assert report["net_roles"]["vdd"]["role"] == "power"
    assert report["net_roles"]["0"]["role"] == "ground"


def test_cli_stdout(capsys):
    assert main([str(BENCH / "rc_lowpass.sp")]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["flat"]["devices_by_type"] == {
        "vsource": 1, "resistor": 1, "capacitor": 1}
