
import models.nmf_std as mstd
import models.mf_fit as mfit
import models.mf_track as mtrack
from utils.linalg import *

class Bd(mstd.Nmf_std):
    """
    Bayesian Decomposition - Bayesian nonnegative matrix factorization Gibbs sampler [16].
    
    In the Bayesian framework knowledge of the distribution of the residuals is stated in terms of likelihood function and
    the parameters in terms of prior densities. In this method normal likelihood and exponential priors are chosen as these 
    are suitable for a wide range of problems and permit an efficient Gibbs sampling procedure. Using Bayes rule, the posterior
    can be maximized to yield an estimate of basis (W) and mixture (H) matrix. However, we are interested in estimating the 
    marginal density of the factors and because the marginals cannot be directly computed by integrating the posterior, an
    MCMC sampling method is used.    
    
    In Gibbs sampling a sequence of samples is drawn from the conditional posterior densities of the model parameters and this
    converges to a sample from the joint posterior. The conditional densities of basis and mixture matrices are proportional 
    to a normal multiplied by an exponential, i. e. rectified normal density. The conditional density of sigma**2 is an inverse 
    Gamma density. The posterior can be approximated by sequentially sampling from these conditional densities. 
    
    Bayesian NMF is concerned with the sampling from the posterior distribution of basis and mixture factors. Algorithm outline
    is: 
        #. Initialize basis and mixture matrix. 
        #. Sample from rectified Gaussian for each column in basis matrix.
        #. Sample from rectified Gaussian for each row in mixture matrix. 
        #. Sample from inverse Gamma for noise variance
        #. Repeat the previous three steps until some convergence criterion is met. 
        
    The sampling procedure could be used for estimating the marginal likelihood, which is useful for model selection, i. e. 
    choosing factorization rank. 
    
    [16] Schmidt, M.N., Winther, O.,  and Hansen, L.K., (2009). Bayesian Non-negative Matrix Factorization. 
        In Proceedings of ICA. 2009, 540-547.
    """

    def __init__(self, **params):
        """
        For detailed explanation of the general model parameters see :mod:`mf_methods`.
        
        The following are algorithm specific model options which can be passed with values as keyword arguments.
        
        :param m: Number of Gibbs samples to compute. Default is 30. 
        :type m: `int`
        :param alpha: The prior for basis matrix (W) of proper dimensions. Default is zeros matrix prior.
        :type alpha: :class:`scipy.sparse.csr_matrix` or :class:`numpy.matrix`
        :param beta: The prior for mixture matrix (H) of proper dimensions. Default is zeros matrix prior.
        :type beta: :class:`scipy.sparse.csr_matrix` or :class:`numpy.matrix`
        :param theta: The prior for :param:`sigma`. Default is 0.
        :type theta: `float`
        :param k: The prior for :param:`sigma`. Default is 0. 
        :type k: `float`
        :param sigma: Initial value for noise variance (sigma**2). Default is 1. 
        :type sigma: `float`  
        :param chains: Number of chains to run. Default is 1.
        :type chains: `int`
        :param skip: Number of initial samples to skip. Default is 100.
        :type skip: `int`
        :param stride: Return every stride'th sample. Default is 1. 
        :type stride: `int`
        :param n_w: Method does not sample from these columns of basis matrix. Default is sampling from all columns. 
        :type n_w: :class:`numpy.ndarray` or list of shape (factorization rank, 1) with logical values
        :param n_h: Method does not sample from these rows of mixture matrix. Default is sampling from all rows. 
        :type n_h: :class:`numpy.ndarray` or list of shape (factorization rank, 1) with logical values
        :param n_sigma: Method does not sample from :param:`sigma`. By default sampling is done. 
        :type ns: logical    
        """
        mstd.Nmf_std.__init__(self, params)
        self.name = "bd"
        self.aseeds = ["random", "fixed", "nndsvd"]
        
    def factorize(self):
        """
        Compute matrix factorization.
         
        Return fitted factorization model.
        """
        self._set_params()
        self.v = multiply(self.V, self.V).sum() / 2.
                
        for _ in xrange(self.n_run):
            self.W, self.H = self.seed.initialize(self.V, self.rank, self.options)
            pobj = cobj = self.objective()
            iter = 0
            while self._is_satisfied(pobj, cobj, iter):
                pobj = cobj
                self.update()
                cobj = self.objective() if not self.test_conv or iter % self.test_conv == 0 else cobj
                iter += 1
            if self.callback:
                self.final_obj = cobj
                mffit = mfit.Mf_fit(self) 
                self.callback(mffit)
            if self.tracker != None:
                self.tracker.append(mtrack.Mf_track(W = self.W.copy(), H = self.H.copy()))
        
        self.n_iter = iter
        self.final_obj = cobj
        mffit = mfit.Mf_fit(self)
        return mffit
        
    def _is_satisfied(self, pobj, cobj, iter):
        """Compute the satisfiability of the stopping criteria based on stopping parameters and objective function value."""
        if self.max_iters and self.max_iters < iter:
            return False
        if self.min_residuals and iter > 0 and cobj - pobj <= self.min_residuals:
            return False
        if iter > 0 and cobj >= pobj:
            return False
        return True
    
    def _set_params(self):
        self.m = self.options.get('m', 30)
        self.alpha = self.options.get('alpha', sp.csr_matrix((self.V.shape[0], self.rank)))
        self.beta = self.options.get('beta', sp.csr_matrix((self.rank, self.V.shape[1])))
        self.theta = self.options.get('theta', .0)
        self.k = self.options.get('k', .0)
        self.sigma = self.options.get('sigma', 1.) 
        self.skip = self.options.get('skip', 100) 
        self.stride = self.options.get('stride', 1)  
        self.chains = self.options.get('chains', 1)
        self.n_w = self.options.get('n_w', np.zeros((self.rank, 1)))
        self.n_h = self.options.get('n_h', np.zeros((self.rank, 1)))
        self.n_sigma = self.options.get('n_sigma', 0)
        self.tracker = [] if self.options.get('track', 0) and self.n_run > 1 else None
        
    def update(self):
        """Update basis and mixture matrix."""
    
    def objective(self):
        """Compute squared Frobenius norm of a target matrix and its NMF estimate.""" 
        return (elop(self.V - dot(self.W, self.H), 2, pow)).sum()