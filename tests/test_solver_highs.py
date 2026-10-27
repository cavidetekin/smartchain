"""HiGHS paket kontrolü (0.7, K-76): sabit LP ve MILP bilinen sonuçla; süre ve iş parçacığı ayarları uygulanıyor."""
import pytest

from app.engine.settings import DEFAULTS, EngineSettings
from app.engine.solvers import highs


@pytest.fixture(scope="module")
def result():
    return highs.smoke_test(time_limit=7.5, threads=1)


def test_lp_known_solution(result):
    lp = result["lp"]
    assert lp["optimal"] and lp["status"] == "Optimal"
    assert lp["objective"] == pytest.approx(36.0)
    assert lp["values"] == pytest.approx([2.0, 6.0])
    assert lp["duals"] == pytest.approx([0.0, 1.5, 1.0])  # gölge fiyatlar (fonksiyon 32-05, 39)


def test_milp_known_solution(result):
    milp = result["milp"]
    assert milp["optimal"]
    assert milp["objective"] == pytest.approx(33.0)  # gevşetilmiş LP 35 olurdu
    assert milp["values"] == pytest.approx([1.0, 6.0])
    assert all(float(v).is_integer() for v in milp["values"])


def test_options_applied(result):
    assert result["solver"] == "HiGHS" and result["version"] == "1.15.1"
    for part in ("lp", "milp"):
        assert result[part]["time_limit"] == pytest.approx(7.5)
        assert result[part]["threads"] == 1


@pytest.mark.parametrize("kwargs", [{"threads": -1}, {"time_limit": 0}])
def test_rejects_invalid_settings(kwargs):
    with pytest.raises(ValueError):
        highs.smoke_test(**kwargs)


def test_check_detects_wrong_result():
    wrong = {"optimal": True, "status": "Optimal", "objective": 35.0, "values": [5 / 3, 6.0]}
    with pytest.raises(highs.SolverCheckError, match="amaç"):
        highs._check("milp", wrong)


def test_solver_threads_setting():
    assert DEFAULTS["SolverThreads"] == 2 and EngineSettings().solver_threads == 2
