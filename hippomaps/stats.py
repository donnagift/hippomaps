import numpy as np
import nibabel as nib
import scipy.io as spio
from scipy.ndimage import rotate
from scipy.ndimage import shift
from scipy.stats import spearmanr, pearsonr
from sklearn.metrics import adjusted_mutual_info_score, adjusted_rand_score
import warnings
import hippomaps.utils
import hippomaps.config
import matplotlib.pyplot as plt
from brainspace.mesh.mesh_io import read_surface
from hippomaps.moran import MoranRandomization
from brainspace.mesh import mesh_elements as me
from pathlib import Path
resourcesdir=str(Path(__file__).parents[1]) + '/resources'

def spin_test(imgfix, imgperm, nperm=1000, metric='pearson', label='hipp', den='0p5mm'):
    """
       Permutation testing of unfolded hippocampus maps.

       Original code by Bradley Karat at https://github.com/Bradley-Karat/Hippo_Spin_Testing
       Karat, B. G., DeKraker, J., Hussain, U., Köhler, S., & Khan, A. R. (2023).
       Mapping the macrostructure and microstructure of the in vivo human hippocampus using diffusion MRI.
       Human Brain Mapping. https://doi.org/10.1002/hbm.26461

       Parameters
       ----------
       imgfix : str or array
           Path to the fixed map, or fixed array map.
       imgperm : str or array
           Path to the fixed map to be permuted, or array map to be permuted.
       nperm : int
           Number of permutations to perform.
       metric : str, optional
           Metric for comparing maps (one of pearson, spearman, adjusted rand, or adjusted mutual info).
           Default is 'pearson'.
       label : str, optional
           Label for the hippocampus ('hipp' or 'dentate'). Default is 'hipp'.
       den : str, optional
           Density of the surface data. Default '0p5mm'.

       Returns
       -------
       metricnull : Null distribution of the specified metric
       permutedimg : All permuted spatial maps at 'unfoldiso' density.
       r_obs :  The observed association between the two aligned maps.

       pval : p-value based on metricnull r_obs.
       """
    if type(imgfix) == str:
        imgfix = nib.load(imgfix).agg_data()
    if type(imgperm) == str:
        imgperm = nib.load(imgperm).agg_data()

    # resmaple to space-unfoldiso
    if den != 'unfoldiso':
        imgperm = hippomaps.utils.density_interp(den, 'unfoldiso', imgperm, label=label, method='nearest')[0]
        imgfix = hippomaps.utils.density_interp(den, 'unfoldiso', imgfix, label=label, method='nearest')[0]  
    imgperm = np.reshape(imgperm, (126, 254))  # get maps to 126x254
    imgfix = np.reshape(imgfix, (126, 254))  # get maps to 126x254

    rotation = np.random.randint(1, 360, nperm)  # generate random rotations
    translate1 = np.random.randint(-63, 64, nperm)  # generate random translations
    translate2 = np.random.randint(-127, 128, nperm)
    permutedimg = np.empty((126, 254, nperm))
    metricnull = np.empty((nperm))

    for ii in range(nperm):
        rotimg = rotate(imgperm, rotation[ii], axes=(1, 0), reshape=False, output=None, order=3, mode='wrap',
                        cval=0.0, prefilter=True)  # rotate image
        transrotimg = shift(rotimg, [translate1[ii], translate2[ii]], output=None, order=3, mode='wrap', cval=0.0,
                            prefilter=True)  # translate image
        permutedimg[:, :, ii] = transrotimg  # this is our permuted image at unfoldiso density

    if metric == 'pearson':
        r_obs = pearsonr(imgfix.flatten(), imgperm.flatten())[0]  
        for ii in range(nperm):
            metricnull[ii] = pearsonr(imgfix.flatten(), permutedimg[:,:,ii].flatten())[0]  
    elif metric == 'spearman':
        r_obs = spearmanr(imgfix.flatten(), imgperm.flatten())[0]  
        for ii in range(nperm):
            metricnull[ii] = spearmanr(imgfix.flatten(), permutedimg[:,:,ii].flatten())[0]  
    elif metric == 'adjusted rand':
        r_obs = adjusted_rand_score(imgfix.flatten(), imgperm.flatten())[0]  
        for ii in range(nperm):
            metricnull[ii] = adjusted_rand_score(imgfix.flatten(), permutedimg[:,:,ii].flatten())[0]  
    elif metric == 'adjusted mutual info':
        r_obs = adjusted_mutual_info(imgfix.flatten(), imgperm.flatten())[0]  
        for ii in range(nperm):
            metricnull[ii] = adjusted_mutual_info(imgfix.flatten(), permutedimg[:,:,ii].flatten())[0]  
    
    # p-value is the sum of all instances where null correspondance is >= observed correspondance / nperm
    pval = np.mean(np.abs(metricnull) >= np.abs(r_obs))  

    return metricnull, permutedimg, pval, r_obs


def moran_test(imgfix, imgperm, nperm=1000, metric='pearson', label='hipp', den='0p5mm'):
    """
       Moran Spectral Randomization
       Moran Spectral Randomization (MSR) computes Moran’s I, a metric for spatial auto-correlation and generates normally distributed data with similar auto-correlation. MSR relies on a weight matrix denoting the spatial proximity of features to one another. Within neuroimaging, one straightforward example of this is inverse geodesic distance i.e. distance along the cortical surface.

       Code from BrainSpace https://brainspace.readthedocs.io/en/latest/python_doc/auto_examples/plot_tutorial3.html
       Vos de Wael, Reinder, Oualid Benkarim, Casey Paquola, Sara Lariviere, Jessica Royer, Shahin Tavakol, Ting Xu et al. "BrainSpace: a toolbox for the analysis of macroscale gradients in neuroimaging and connectomics datasets." Communications biology 3, no. 1 (2020): 103.

       Parameters
       ----------
       imgfix : str or array
           Path to the fixed map, or fixed array map.
       imgperm : str or array
           Path to the fixed map to be permuted, or array map to be permuted.
       nperm : int
           Number of permutations to perform.
       metric : str, optional
           Metric for comparing maps (one of pearson, spearman, adjusted rand, or adjusted mutual info).
           Default is 'pearson'.
       label : str, optional
           Label for the hippocampus ('hipp' or 'dentate'). Default is 'hipp'.
       den : str, optional
           Density of the surface data. Default '0p5mm'.

       Returns
       -------
       metricnull : Null distribution of the specified metric
       permutedimg : All permuted spatial maps at 'unfoldiso' density.
       r_obs :  The observed association between the two aligned maps.

       pval : p-value based on metricnull r_obs.
       """
    if type(imgfix) == str:
        imgfix = nib.load(imgfix).agg_data()
    if type(imgperm) == str:
        imgperm = nib.load(imgperm).agg_data()
    
    # load reference surface to get geodesic distance
    surf = read_surface(f"{resourcesdir}/canonical_surfs/tpl-avg_space-canonical_den-{den}_label-hipp_midthickness.surf.gii")
    # wrap concenient brainspace function for weights (geodesic distance) and MRS
    weights = me.get_ring_distance(surf, n_ring=1)
    weights.data **= -1
    msr = MoranRandomization(n_rep=nperm, spectrum='all')
    msr.fit(weights)

    # get observed correlation
    r_obs = spearmanr(imgfix, imgperm, nan_policy='omit')[0]

    # randomize
    imgperm_rand = msr.randomize(imgperm)
    metricnull = np.empty((nperm))
    for d in range(nperm):
        metricnull[d] = spearmanr(imgfix, imgperm_rand[d,:])[0]

    # p-value is the sum of all instances where null correspondance is >= observed correspondance / nperm
    pval = np.mean(np.abs(metricnull) >= np.abs(r_obs))  

    return metricnull, imgperm_rand, pval, r_obs

def contextualize2D(taskMaps, n_topComparison=3, permTest=True, nperm=1000, plot2D=True):
    """
       Compares the present maps to thoes in the inital HippoMaps release

       Parameters
       ----------
       taskMaps : a VxT matrix of intensities. T is the number of maps to examine
       n_topComparison : int, optional
           Top N features for which to reurn comparisons (Pearson's R and p)
       plot2D : bool
           Whether to plot the new maps in context of other maps

       Returns
       -------
       topFeatures : Names of most similar intialized features
       topR : Correpsonding Pearson's R values
       topP : Corresponding p values (spin test)
       APcorr : Correlation with AP coordinates
       Subfscorr : Max correlation with subfields (Spearmann)
       ax : axis handle
       """
    nT = taskMaps.shape[1]

    # load required data
    contextHM = np.load('../resources/2Dcontextualize/initialHippoMaps.npz')
    # resample input data if needed
    nVref,iVref = hippomaps.config.get_nVertices(['hipp'],'0p5mm')
    if taskMaps.shape[0] != nVref:
        taskMapsresamp = np.ones((nVref,nT))*np.nan
        for t in range(nT):
            taskMapsresamp[:,t],_,_ = hippomaps.utils.density_interp('2mm','0p5mm',taskMaps[:,t], label='hipp')
    else:
        taskMapsresamp = taskMaps

    # compute correlations with extant features
    topFeatures = np.ones((nT,n_topComparison), dtype='object')
    topR = np.ones((nT,n_topComparison))*np.nan
    topP = np.ones((nT,n_topComparison))*np.nan
    if n_topComparison >0:
        p = np.ones((taskMaps.shape[1],len(contextHM['features'])))
        R = np.ones((taskMaps.shape[1],len(contextHM['features'])))
        for i in range(taskMaps.shape[1]):
            for j in range(len(contextHM['features'])):
                if permTest:
                    _,_,p[i,j],R[i,j] = hippomaps.stats.spin_test(taskMapsresamp[:,i],contextHM['featureData'][:,j], nperm)
                else:
                    R[i,j],p[i,j] = pearsonr(taskMapsresamp[:,i],contextHM['featureData'][:,j])
        # get ordering of the closest n_topComparison neighbours
        for t in range(nT):
            order = np.argsort(np.abs(R[t,:]))[::-1]
            for c in range(n_topComparison):
                topFeatures[t,c] = contextHM['features'][order[c]]
                topR[t,c] = R[t,order[c]]
                topP[t,c] = p[t,order[c]]
            
    # get position of new features on 2D space axes
    APcorr = spearmanr(np.concatenate((taskMapsresamp,contextHM['AP'].reshape([-1,1])),axis=1))[0][nT:,:nT]
    APcorr = np.abs(APcorr)
    Subfscorr = spearmanr(np.concatenate((taskMapsresamp,contextHM['subfields_permuted']),axis=1))[0][nT:,:nT]
    Subfscorr = np.nanmax(np.abs(Subfscorr),axis=0)

    # plot in space
    fig, ax = plt.subplots(figsize=(8,8))
    if plot2D:
        ax.spines[['right', 'top']].set_visible(False)
        ax.scatter(contextHM['axiscorrAPPD'][0],contextHM['subfieldsmaxcorr'],c=contextHM['colors'],cmap='Set3',s=200)
        plt.ylabel("absolute subfield correlation (Spearmann's R)")
        plt.xlabel("absolute AP correlation (Pearnson's R)")
        for f,feature in enumerate(contextHM['features']):
            ax.annotate(str(int(contextHM['feature_n'][f])), (contextHM['axiscorrAPPD'][0,f]-.008, contextHM['subfieldsmaxcorr'][f]-.007))
        ax.scatter(APcorr,Subfscorr,color='k',s=200);
        for t in range(nT):
            ax.annotate(str(t), (APcorr[0,t]-.008, Subfscorr[t]-.007),color='w')
            
    return topFeatures, topR, topP, APcorr, Subfscorr, ax
