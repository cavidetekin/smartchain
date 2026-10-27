"""HiGHS (highspy, MIT) — adaptörün yeri (K-76). Adaptör 10.5'te; şimdilik paket kontrolü.

smoke_test, çözücünün kurulmuş ortamda (internetsiz paket) çalıştığını ve süre ile iş parçacığı ayarlarının
uygulandığını iki sabit, sonucu bilinen modelle doğrular (docs/09-motor-arayuzu.md · Çözücü):
  LP:   max 3x + 5y;  x ≤ 4,  2y ≤ 12,  3x + 2y ≤ 18                  → x = 2, y = 6, amaç 36, gölge fiyatlar 0, 1,5, 1
  MILP: aynı model, 3x + 2y ≤ 17, x ve y tamsayı                        → x = 1, y = 6, amaç 33 (gevşetilmiş LP 35)
"""
import time

import highspy
import numpy as np

TOLERANCE = 1e-6

# (değişken indisleri, katsayılar, üst sınır)
LP_ROWS = [([0], [1.0], 4.0), ([1], [2.0], 12.0), ([0, 1], [3.0, 2.0], 18.0)]
MILP_ROWS = LP_ROWS[:2] + [([0, 1], [3.0, 2.0], 17.0)]
EXPECTED = {
    "lp": {"objective": 36.0, "values": [2.0, 6.0], "duals": [0.0, 1.5, 1.0]},
    "milp": {"objective": 33.0, "values": [1.0, 6.0]},
}


class SolverCheckError(RuntimeError):
    """Çözücü kurulmuş ortamda beklenen sonucu vermedi."""


def _option(h: highspy.Highs, name: str):
    value = h.getOptionValue(name)
    return value[1] if isinstance(value, tuple) else value  # highspy sürümleri arasında dönüş biçimi değişiyor


def _solve(rows, integer: bool, time_limit: float, threads: int) -> dict:
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("log_to_console", False)
    h.setOptionValue("time_limit", float(time_limit))
    h.setOptionValue("threads", int(threads))
    inf = highspy.kHighsInf
    h.addVars(2, np.array([0.0, 0.0]), np.array([inf, inf]))
    h.changeColsCost(2, np.array([0, 1], dtype=np.int32), np.array([3.0, 5.0]))
    h.changeObjectiveSense(highspy.ObjSense.kMaximize)
    for idx, coef, upper in rows:
        h.addRow(-inf, upper, len(idx), np.array(idx, dtype=np.int32), np.array(coef))
    if integer:
        h.changeColsIntegrality(2, np.array([0, 1], dtype=np.int32),
                                np.array([highspy.HighsVarType.kInteger] * 2))
        h.setOptionValue("mip_rel_gap", 0.0)
    started = time.perf_counter()
    h.run()
    solution = h.getSolution()
    result = {
        "status": h.modelStatusToString(h.getModelStatus()),
        "optimal": h.getModelStatus() == highspy.HighsModelStatus.kOptimal,
        "objective": h.getInfo().objective_function_value,
        "values": list(solution.col_value),
        "seconds": round(time.perf_counter() - started, 4),
        "time_limit": _option(h, "time_limit"),
        "threads": _option(h, "threads"),
    }
    if not integer:
        result["duals"] = list(solution.row_dual)
    return result


def _check(name: str, got: dict) -> None:
    exp = EXPECTED[name]
    if not got["optimal"]:
        raise SolverCheckError(f"{name.upper()} optimal değil: {got['status']}")
    pairs = [("amaç", [got["objective"]], [exp["objective"]]), ("değerler", got["values"], exp["values"])]
    if "duals" in exp:
        pairs.append(("gölge fiyatlar", got["duals"], exp["duals"]))
    for label, a, b in pairs:
        if len(a) != len(b) or any(abs(x - y) > TOLERANCE for x, y in zip(a, b)):
            raise SolverCheckError(f"{name.upper()} {label} beklenen {b}, gelen {a}")


def smoke_test(time_limit: float = 10.0, threads: int = 1) -> dict:
    """LP ve MILP'yi çözer, bilinen sonuçla doğrular; tutmazsa SolverCheckError.

    time_limit: çözücüye geçen süre sınırı (sn) — gerçek hesapta işin süre bütçesinden gelir (fonksiyon 34).
    threads: iş parçacığı sayısı — gerçek hesapta SolverThreads sistem ayarından; 0 HiGHS'e bırakır.
    """
    if time_limit <= 0:
        raise ValueError("time_limit sıfırdan büyük olmalı")
    if threads < 0:
        raise ValueError("threads 0 (otomatik) ya da pozitif olmalı")
    lp = _solve(LP_ROWS, False, time_limit, threads)
    _check("lp", lp)
    milp = _solve(MILP_ROWS, True, time_limit, threads)
    _check("milp", milp)
    return {"solver": "HiGHS", "version": highspy.Highs().version(), "lp": lp, "milp": milp}
