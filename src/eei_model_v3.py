"""Element-level exploration and imitation with stimulus spread: the model.

This is the model cell shared by eight of the ten notebooks, saved as a module. Every function is named
after the equation it implements in the manuscript, and the equation numbers are given in the docstrings.
Equations S1 and S2 are those of the supplementary information. The commitment pair of the manuscript is
phi0 and phi1 here.
"""
import numpy as np
import networkx as nx

LOG2 = np.log(2.0)


# ----------------------------------------------------------------------
# measures (definitions of the second study)
# ----------------------------------------------------------------------
def control_entropy(v):
    """Control entropy in bits of a non-negative vector of shares (Eq. 11)."""
    v = np.asarray(v, float)
    tot = v.sum()
    if tot <= 0:
        return 0.0
    p = v / tot
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def eigen_shares(W):
    """Shares from the leading eigenvector of a symmetric coupling matrix."""
    vals, vecs = np.linalg.eigh(W)
    v = np.abs(vecs[:, -1])
    return v / v.sum()


def adjacency_measures(A, W):
    """Measures read from the unweighted structure, computed as in Table 1 of the
    control-entropy paper: eigenvector weighting on the largest connected component,
    degree assortativity on the whole graph."""
    G = nx.from_numpy_array(A.astype(int))
    deg = A.sum(axis=1)
    s = W.sum(axis=1)
    iu, ju = np.nonzero(np.triu(A, 1))

    def edge_corr(v):
        x, y = np.concatenate([v[iu], v[ju]]), np.concatenate([v[ju], v[iu]])
        return float(np.corrcoef(x, y)[0, 1]) if x.std() > 1e-12 else float('nan')

    r_deg, r_str = edge_corr(deg.astype(float)), edge_corr(s)
    if not nx.is_connected(G):
        G = G.subgraph(max(nx.connected_components(G), key=len)).copy()
    c = nx.eigenvector_centrality_numpy(G)
    v = np.abs(np.array([c[n] for n in G.nodes()]))
    return dict(H_adj=control_entropy(v), r_deg=float(r_deg), r_str=r_str, gc=G.number_of_nodes())


# ----------------------------------------------------------------------
# the five rules, one function each
# ----------------------------------------------------------------------
def ring_lattice(N, k):
    """Regular ring lattice: every element coupled to its k nearest neighbours."""
    return nx.to_numpy_array(nx.watts_strogatz_graph(N, k, 0.0), dtype=bool)


def softmax_allocation(A, beta, shat):
    """Eq 1. Element i splits one unit of coupling over its partners j with weights
    exp(beta_i * shat_j). beta_i = 0 gives even coupling."""
    L = np.where(A, beta[:, None] * shat[None, :], -np.inf)
    L = L - L.max(axis=1, keepdims=True)
    E = np.where(A, np.exp(L), 0.0)
    return E / E.sum(axis=1, keepdims=True)


def commitment(phi0, phi1, C, fm):
    """Eq 2. Commitment of an element, in the linear form of the published model,
    f = phi0 + phi1 * C, truncated to [0, 1 - fm]."""
    return np.clip(phi0 + phi1 * C, 0.0, 1.0 - fm)


def protection(f, c, pmax, chalf):
    """Eq 8. Saturating protection bought by committed capability f * c."""
    x = f * c
    return np.where(x > 0, pmax / (1.0 + chalf / np.maximum(x, 1e-12)), 0.0)


def fermi(dc, s):
    """Eq 10. Probability of copying a partner whose capability is higher by dc."""
    return 1.0 / (1.0 + np.exp(-s * dc))


def logistic(z, g, theta):
    """Response function of an element, used inside the spread (Eq 5)."""
    return 1.0 / (1.0 + np.exp(-g * (z - theta)))


class ElementModel:
    """Network-agent model of element-level exploration and imitation.

    Each element holds
      beta_i        direction of coupling (0 = even coupling, > 0 = toward stronger partners)
      phi0_i, phi1_i commitment strategy, giving f_i = phi0_i + phi1_i * C_i
      c_i           capability, the accumulated stimulation it compares with partners
    Each coupling (i, j) holds a weight w_ij.
    """

    def __init__(self, N=100, k=6, seed=0,
                 pr=0.3, pe=0.05, sigma=0.1, sigma_f=0.01, s=2.0,   # strategy dynamics
                 M=10, rho=0.5, nE=5, switch=None, psi=0.3,        # feedback, two channels
                 gamma=1.0, pn=0.02, pl=0.3, lam=1.0, g=4.0, theta=1.0,   # seeding and spread
                 fm=0.1, pmax=1.0, chalf=0.1, f0=0.1,              # capability and protection
                 eta=0.05, delta=0.01, w0=1.0,                     # consolidation
                 pw=2.0, kmin=2, loss=1.0,                         # pruning and its cost
                 spread=True, two_part=True):
        self.p = dict(N=N, k=k, pr=pr, pe=pe, sigma=sigma, sigma_f=sigma_f, s=s, M=M, rho=rho,
                      nE=nE, switch=switch, psi=psi, gamma=gamma, pn=pn, pl=pl, lam=lam, g=g,
                      theta=theta, fm=fm, pmax=pmax, chalf=chalf, f0=f0, eta=eta, delta=delta,
                      w0=w0, pw=pw, kmin=kmin, loss=loss, spread=spread, two_part=two_part)
        self.rng = np.random.default_rng(seed)
        self.N, self.k = N, k
        self.A = ring_lattice(N, k)
        self.W = self.A.astype(float) * w0
        self.beta = np.zeros(N)
        self.phi0 = np.full(N, f0)
        self.phi1 = np.zeros(N)
        self.c = np.ones(N)
        self.x = np.zeros(N)          # activation of the previous step
        self.v = np.ones(N) / np.sqrt(N)   # leading eigenvector, kept warm
        self.t = 0
        self.n_act = 0.0
        self.n_rounds = 0.0
        self.set_essential(self.rng.choice(N, nE, replace=False))

    # ---------- state helpers ----------
    def set_essential(self, E):
        self.E = np.asarray(E)
        self.isE = np.zeros(self.N, bool)
        self.isE[self.E] = True

    def strengths(self):
        return self.W.sum(axis=1)

    def shat(self):
        s = self.strengths()
        return s / s.max()

    def centrality(self, iters=8):
        """Leading eigenvector of W by power iteration, warm started, scaled to a
        maximum of one. This is the C of the commitment rule (Eq 2)."""
        v = self.v
        for _ in range(iters):
            v = self.W @ v
            n = np.linalg.norm(v)
            if n < 1e-12:
                v = np.ones(self.N) / np.sqrt(self.N)
                break
            v = v / n
        self.v = np.abs(v)
        return self.v / max(self.v.max(), 1e-12)

    def allocation(self):
        return softmax_allocation(self.A, self.beta, self.shat())

    # ---------- one step ----------
    def feedback(self):
        """Eq 3. Two channels of information.
        Process feedback is intrinsic: every element receives afferent input in
        proportion to its own activation in the previous step.
        Result feedback is augmented: M packets, each landing on a task-essential
        element with probability rho and on any element otherwise."""
        p, rng = self.p, self.rng
        u = p['psi'] * self.x.copy()
        if p['M'] > 0:
            to_E = rng.random(p['M']) < p['rho']
            tgt = np.where(to_E, rng.choice(self.E, p['M']), rng.integers(0, self.N, p['M']))
            u = u + np.bincount(tgt, minlength=self.N).astype(float)
        return u

    def spread(self, u, a):
        """Eq 4 and Eq 5. Stimulus is seeded where information arrives and then
        travels along the couplings.
        Seeding: element i is stimulated with probability 1 - (1 - p_n) exp(-gamma u_i),
        so an element fires spontaneously at rate p_n and more often when information
        reaches it.
        Spread: an element already stimulated passes activation to partner j with
        the coupling it allocates, and j responds with probability
        pl * logistic(g (d_j - theta)). Each element activates at most once per step.
        The cascade is run to completion inside the step."""
        p, rng, N = self.p, self.rng, self.N
        act = rng.random(N) < (1.0 - (1.0 - p['pn']) * np.exp(-p['gamma'] * u))   # Eq 4
        if not p['spread']:
            self.n_act, self.n_rounds = float(act.sum()), 0.0
            return act
        frontier = act.copy()
        rounds = 0
        while frontier.any() and rounds < 20:
            # drive reaching each candidate through the allocation of active elements
            d = p['lam'] * self.k * (frontier @ a)
            prob = p['pl'] * logistic(d, p['g'], p['theta'])       # Eq 5
            new = (rng.random(N) < prob) & ~act
            act |= new
            frontier = new
            rounds += 1
        self.n_act, self.n_rounds = float(act.sum()), float(rounds)
        return act

    def step(self):
        p, rng, N = self.p, self.rng, self.N
        if p['switch'] and self.t > 0 and self.t % p['switch'] == 0:
            self.set_essential(rng.choice(N, p['nE'], replace=False))

        C = self.centrality()
        a = self.allocation()                                     # Eq 1
        f = commitment(self.phi0, self.phi1, C, p['fm']) if p['two_part'] else np.zeros(N)  # Eq 2
        u = self.feedback()                                       # Eq 3
        act = self.spread(u, a)                                   # Eq 4, Eq 5
        x = act.astype(float)
        self.x = x

        # Eq 6. Payoff is the stimulation the element gathers. It reaches partners
        # through its own allocation and it integrates in proportion to the coupling
        # it holds, so both the direction and the amount of coupling enter.
        s = self.strengths()
        pay = (s / s.mean()) * (a @ x)
        self.c = pay + np.clip(1.0 - p['fm'] - f, 0.0, None) * self.c   # Eq 7

        # Eq 8 and Eq 9. Commitment protects a coupling against decay.
        P = protection(f, self.c, p['pmax'], p['chalf'])
        Pij = 0.5 * (P[:, None] + P[None, :])
        abar = 0.5 * (a + a.T)
        self.W = np.where(self.A,
                          p['w0'] + (1 - p['delta'] * (1 - Pij)) * (self.W - p['w0'])
                          + p['eta'] * self.k * abar * np.outer(x, x), 0.0)

        # Eq S1. Long-term change: a coupling falls out of use, and unless the
        # capability committed to it holds it, it is lost and replaced elsewhere.
        n_rw = int(p['pw']) + (1 if rng.random() < p['pw'] - int(p['pw']) else 0)
        for _ in range(n_rw):
            self._rewire(P)

        # Eq 10. Imitation along a coupling, synchronous, two independent passes.
        b_old, f0_old, f1_old, c_old = self.beta.copy(), self.phi0.copy(), self.phi1.copy(), self.c.copy()
        for i in np.flatnonzero(rng.random(N) < p['pr']):
            nb = np.flatnonzero(self.A[i])
            j = nb[rng.integers(nb.size)]
            if rng.random() < fermi(c_old[j] - c_old[i], p['s']):
                self.beta[i] = b_old[j]
        if p['two_part']:
            for i in np.flatnonzero(rng.random(N) < p['pr']):
                nb = np.flatnonzero(self.A[i])
                j = nb[rng.integers(nb.size)]
                if rng.random() < fermi(c_old[j] - c_old[i], p['s']):
                    self.phi0[i], self.phi1[i] = f0_old[j], f1_old[j]

        # Eq S2. Exploration of both parts of the strategy.
        ex = rng.random(N) < p['pe']
        self.beta[ex] += rng.normal(0.0, p['sigma'], ex.sum())
        if p['two_part']:
            ex0 = rng.random(N) < p['pe']
            self.phi0[ex0] += rng.normal(0.0, p['sigma_f'], ex0.sum())
            ex1 = rng.random(N) < p['pe']
            self.phi1[ex1] += rng.normal(0.0, p['sigma_f'], ex1.sum())
        self.t += 1
        return x

    def _rewire(self, P):
        """One element drops its weakest coupling, unless protection holds it, and
        attaches to a new partner chosen with exp(beta_i * shat_j)."""
        p, rng = self.p, self.rng
        i = rng.integers(self.N)
        deg = self.A.sum(axis=1)
        nb = np.flatnonzero(self.A[i])
        nb = nb[deg[nb] > p['kmin']]
        if deg[i] <= p['kmin'] or nb.size == 0:
            return
        j = nb[np.argmin(self.W[i, nb])]
        if rng.random() < 0.5 * (P[i] + P[j]):     # the coupling is held
            return
        # the route is lost, and with it the capability the two elements had built
        # through it. With loss = 1 this is the capability loss of the published model.
        self.c[i] *= (1.0 - p['loss'])
        self.c[j] *= (1.0 - p['loss'])
        cand = np.flatnonzero(~self.A[i])
        cand = cand[cand != i]
        if cand.size == 0:
            return
        z = self.beta[i] * self.shat()[cand]
        w = np.exp(z - z.max())
        new = rng.choice(cand, p=w / w.sum())
        self.A[i, j] = self.A[j, i] = False
        self.W[i, j] = self.W[j, i] = 0.0
        self.A[i, new] = self.A[new, i] = True
        self.W[i, new] = self.W[new, i] = p['w0']

    # ---------- measures ----------
    def measures(self, adj=False):
        s = self.strengths()
        deg = self.A.sum(axis=1)
        top = np.argsort(s)[-len(self.E):]
        nbE = self.A[self.E].any(axis=0) & ~self.isE
        tot = s.sum()
        C = self.centrality()
        f = commitment(self.phi0, self.phi1, C, self.p['fm'])
        return dict(H_str=control_entropy(s), H_eig=control_entropy(eigen_shares(self.W)),
                    H_deg=control_entropy(deg), kappa=(deg ** 2).mean() / deg.mean(),
                    beta_mean=self.beta.mean(), beta_var=self.beta.var(),
                    f_mean=float(f.mean()), phi0_mean=float(self.phi0.mean()),
                    phi1_mean=float(self.phi1.mean()), c_mean=float(self.c.mean()),
                    act=self.n_act / self.N, rounds=self.n_rounds,
                    hub_align=self.isE[top].mean(),
                    share_E=s[self.isE].sum() / tot, share_nbE=s[nbE].sum() / tot,
                    **(adjacency_measures(self.A, self.W) if adj else {}))

    def run(self, T, every=25, adj=False):
        rec = {}
        for step in range(T):
            self.step()
            if step % every == 0 or step == T - 1:
                m = self.measures(adj=adj)
                m['t'] = self.t
                for key, v in m.items():
                    rec.setdefault(key, []).append(v)
        return {key: np.array(v) for key, v in rec.items()}


def replicate(T, seeds, adj=True, **kw):
    """Run the model for several seeds and return the final measures."""
    out = []
    for sd in seeds:
        m = ElementModel(seed=sd, **kw)
        for _ in range(T):
            m.step()
        out.append(m.measures(adj=adj))
    return {key: np.array([o[key] for o in out]) for key in out[0]}
