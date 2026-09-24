# Interactive Components

## Code

```{.python .run #cell-matrix}
import numpy as np
A = np.array([[2, 1], [1, 3]])
print("eigenvalues:", np.linalg.eigvals(A))
A.T @ A
```

A later cell sees earlier variables:

```{.python .run #cell-plot}
import matplotlib.pyplot as plt
xs = np.linspace(0, 2 * np.pi, 100)
plt.plot(xs, np.sin(xs))
plt.title("sin")
```

A plain listing stays a listing:

```python
print("not runnable")
```

## Plots

::: {.plot #plot-wave fn="sin(a*x); a*cos(x)/2" x="-6.28,6.28" y="-2,2" params="a=1:0..3"}
The curves \( \sin(ax) \) and \( \tfrac{a}{2}\cos x \).
:::

::: {.plot fn="x^3 - 3*x"}
:::

## Widget

::: {#thm-area}
[Area Scaling]

A linear map of the plane scales areas by \( |\det A| \).

::: {.widget src="widgets/linear-map.js" matrix="2,1,0.5,1.5"}
::: {.print}
The unit square is mapped to the parallelogram spanned by the columns of \( A \).
:::
:::
:::

::: {.proof}
By @thm-main, the determinant is what it is. This proof citation is the fixture's only
cross-chapter **hard** edge, so the dependency graph and every reading path over the
fixture rest on it.
:::

::: {.remark}
@def-thing is named here and nowhere used, which makes this a **soft** edge: the graph
carries it, and no reading path follows it.
:::

::: {.remark}
Compare @thm-aside, which no proof is allowed to lean on.
:::
