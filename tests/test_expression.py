"""
The plot expression grammar exists twice: templates/html/components/expression.js (web)
and filters/components.lua (PDF). These tests evaluate the same expressions with both
and compare the results. Needs node and pandoc.
"""

import json
import math
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent

CASES = [
    ("x^2 - 3*x + 1", {}),
    ("-x^2", {}),
    ("2^3^2", {}),
    ("sin(a*x)/2 + cos(x)", {"a": 1.5}),
    ("exp(-x^2/2)/sqrt(2*pi)", {}),
    ("log(e^x) + abs(-x)", {}),
    ("tanh(x) - atan(x)*a", {"a": -0.25}),
    ("1.5e1*x/.5", {}),
]
X_VALUES = [-2.0, -0.5, 0.0, 0.75, 1.9]


@unittest.skipUnless(shutil.which("node") and shutil.which("pandoc"), "needs node and pandoc")
class TestExpressionParity(unittest.TestCase):

    def js_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / "expression.mjs"
            shutil.copy(ENGINE_ROOT / "templates/html/components/expression.js", module)
            script = f"""
                import {{ compile }} from {json.dumps(module.as_uri())};
                const cases = {json.dumps(CASES)}, xs = {json.dumps(X_VALUES)};
                console.log(JSON.stringify(cases.map(([src, params]) => {{
                    const f = compile(src, Object.keys(params));
                    return xs.map(x => f({{...params, x}}));
                }})));
            """
            result = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def pgf_expressions(self):
        """Run the Lua filter on plots and read the pgfplots expressions it writes."""
        blocks = []
        for source, params in CASES:
            spec = ", ".join(f"{k}={v}:-5..5" for k, v in params.items())
            blocks.append(f'::: {{.plot fn="{source}" params="{spec}"}}\n:::\n')
        result = subprocess.run(
            ["pandoc", "-f", "markdown", "-t", "latex", "--lua-filter", str(ENGINE_ROOT / "filters/components.lua")],
            input="\n".join(blocks), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        expressions = [line.split("{", 1)[1].rsplit("}", 1)[0]
                       for line in result.stdout.splitlines() if line.startswith(r"\addplot")]
        self.assertEqual(len(expressions), len(CASES), result.stdout + result.stderr)
        return expressions

    @staticmethod
    def eval_pgf(expression, x):
        """Evaluate the pgfplots syntax the filter emits (fully parenthesized) in Python."""
        python = expression.replace("^", "**")
        names = {name: getattr(math, name) for name in
                 ("sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "exp", "sqrt")}
        names.update(ln=math.log, abs=abs, pi=math.pi, e=math.e, x=x)
        return eval(python, {"__builtins__": {}}, names)

    def test_web_and_pdf_agree(self):
        js = self.js_values()
        for (source, _), expression, web_values in zip(CASES, self.pgf_expressions(), js):
            for x, web in zip(X_VALUES, web_values):
                with self.subTest(expression=source, x=x):
                    self.assertAlmostEqual(self.eval_pgf(expression, x), web, places=9)


if __name__ == "__main__":
    unittest.main()
