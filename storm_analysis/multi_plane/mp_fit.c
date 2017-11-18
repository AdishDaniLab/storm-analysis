/*
 * Fit multiple, possibly overlapping, PSFs to image data 
 * from multiple planes.
 *
 * Most of the work is done using one of:
 *  1. psf_fft/fft_fit.c
 *  2. pupilfn/pupil_fit.c
 *  3. spliner/cubic_fit.c
 *
 * The expectation is that there will be n_channels copies of
 * each input peak, organized by channel, so for example
 * if there are 3 peaks and 2 channels the peak array would 
 * be [peak1_c1, peak2_c1, peak3_c1, peak1_c2, peak2_c2, peak2_c3].
 * This analysis will then keep the groups of peaks in sync,
 * i.e. peak1_c1 and peak1_c2 will have the same peak status
 * (RUNNING, CONVERGED, ERROR), z value and possibly height. And 
 * their x, y coordinates will be the same after affine 
 * transformation.
 *
 * Proper initialization involves multiple steps:
 *  1. mpInitialize()
 *  2. mpInitializeXXChannel() for each channel.
 *  3. mpSetTransforms() to configure affine transforms between 
 *       channels.
 *  4. mpSetWeights() to set z dependent channel parameter
 *       weighting factors.
 *  5. mpSetWeightsIndexing() to set how to go from a peaks
 *       z value to the correct index in the weighting array.
 *
 * Hazen 10/17
 */

#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <math.h>

#include "../psf_fft/fft_fit.h"
#include "../pupilfn/pupil_fit.h"
#include "../spliner/cubic_fit.h"

typedef struct mpFit
{
  int im_size_x;                /* Image size in x (the fast axis). */
  int im_size_y;                /* Image size in y (the slow axis). */
  
  int independent_heights;      /* Flag for independent peak heights. */
  
  int n_channels;               /* The number of different channels / image planes. */
  int n_weights;                /* The number of (z) weight values. */
  
  int nfit;                     /* The number of peaks to fit per channel. The total 
				   number of peaks is n_channels * nfit. */

  double w_z_offset;            /* Offset value to convert peak z to a weight index. */
  double w_z_scale;             /* Scale value to convert peak z to a weight index. */

  double tolerance;             /* Fit tolerance. */

  double zmin;                  /* Minimum allowed z value, units are fitter dependent. */
  double zmax;                  /* Maximum allowed z value, units are fitter dependent. */
  
  double clamp_start[NFITTING]; /* Starting value for the peak clamp values. */

  double *xt_0toN;              /* Transform x coordinate from channel 0 to channel N. */
  double *yt_0toN;              /* Transform y coordinate from channel 0 to channel N. */
  double *xt_Nto0;              /* Transform x coordinate from channel N to channel 0. */
  double *yt_Nto0;              /* Transform y coordinate from channel N to channel 0. */

  double *w_bg;                 /* Per channel z dependent weighting for the background parameter. */
  double *w_h;                  /* Per channel z dependent weighting for the height parameter. */
  double *w_x;                  /* Per channel z dependent weighting for the x parameter. */
  double *w_y;                  /* Per channel z dependent weighting for the y parameter. */
  double *w_z;                  /* Per channel z dependent weighting for the z parameter. */
  double *heights;              /* Per channel heights for parameter weighting. */

  double **jacobian;            /* Storage for the jacobian calculations. */
  double **w_jacobian;          /* Storage for copies of the jacobians. */
  double **hessian;             /* Storage for the hessian calculations. */
  double **w_hessian;           /* Storage for copies of the jacobians. */
  
  fitData **fit_data;           /* Array of pointers to fitData structures. */

  void (*fn_cleanup)(struct fitData *);                         /* Function for cleaning up fitting for a particular channel. */
  void (*fn_newpeaks)(struct fitData *, double *, char *, int); /* Function for adding new peaks for a particular channel. */
  void (*fn_update)(struct mpFit *);                            /* Function for updating the parameters of the working peaks. */
  void (*fn_zrange)(struct fitData *);                          /* Function for enforcing the z range. */
  
} mpFit;


void mpCleanup(mpFit *);
void mpCopyFromWorking(mpFit *, int, int);
mpFit *mpInitialize(double *, double, int, int, int, int);
void mpInitializePSFFFTChannel(mpFit *, psfFFT *, double *, int);
void mpInitializePupilFnChannel(mpFit *, pupilData *, double *, double, double, int);
void mpInitializeSplineChannel(mpFit *, splineData *, double *, int);
void mpIterateLM(mpFit *);
void mpIterateOriginal(mpFit *);
void mpNewPeaks(mpFit *, double *, char *, int);
void mpResetWorkingPeaks(mpFit *, int);
void mpSetTransforms(mpFit *, double *, double *, double *, double *);
void mpSetWeights(mpFit *, double *, double *, double *, double *, double *, int);
void mpSetWeightsIndexing(mpFit *, double, double);
void mpUpdate(mpFit *);
void mpUpdateFixed(mpFit *);
void mpUpdateIndependent(mpFit *);


/*
 * mpCleanup()
 *
 * Clean up at the end of the analysis.
 */
void mpCleanup(mpFit *mp_fit)
{
  int i;

  /* Call PSF specific cleanup. */
  for(i=0;i<mp_fit->n_channels;i++){
    mp_fit->fn_cleanup(mp_fit->fit_data[i]);
  }

  /* Free affine transform arrays. */
  free(mp_fit->xt_0toN);
  free(mp_fit->yt_0toN);
  free(mp_fit->xt_Nto0);
  free(mp_fit->yt_Nto0);

  /* Free weight arrays. */
  free(mp_fit->w_bg);
  free(mp_fit->w_h);
  free(mp_fit->w_x);
  free(mp_fit->w_y);
  free(mp_fit->w_z);
  free(mp_fit->heights);

  /* Free jacobian / hessian storage. */
  for(i=0;i<mp_fit->n_channels;i++){
    free(mp_fit->jacobian[i]);
    free(mp_fit->w_jacobian[i]);
    free(mp_fit->hessian[i]);
    free(mp_fit->w_hessian[i]);
  }
  free(mp_fit->jacobian);
  free(mp_fit->w_jacobian);
  free(mp_fit->hessian);
  free(mp_fit->w_hessian);
  
  free(mp_fit->fit_data);
  free(mp_fit);
}


/*
 * mpCopyFromWorking()
 *
 * Copy the working peak into the indicated peak. This will also
 * set the status of all the (paired) peaks to the same value.
 */
void mpCopyFromWorking(mpFit *mp_fit, int index, int status)
{
  int i;
  fitData *fit_data;

  for(i=0;i<mp_fit->n_channels;i++){
    fit_data = mp_fit->fit_data[i];
    fit_data->working_peak->status = status;
    fit_data->fn_copy_peak(fit_data->working_peak, &fit_data->fit[index]);
  }
}


/*
 * mpInitialize()
 *
 * Create and return the mpFit structure to use for fitting.
 */
mpFit *mpInitialize(double *clamp, double tolerance, int n_channels, int independent_heights, int im_size_x, int im_size_y)
{
  int i;
  mpFit *mp_fit;

  mp_fit = (mpFit *)malloc(sizeof(mpFit));

  mp_fit->im_size_x = im_size_x;
  mp_fit->im_size_y = im_size_y;
  mp_fit->independent_heights = independent_heights;
  mp_fit->n_channels = n_channels;
  mp_fit->w_z_offset = 0.0;
  mp_fit->w_z_scale = 0.0;
  mp_fit->tolerance = tolerance;

  mp_fit->xt_0toN = (double *)malloc(3*n_channels*sizeof(double));
  mp_fit->yt_0toN = (double *)malloc(3*n_channels*sizeof(double));
  mp_fit->xt_Nto0 = (double *)malloc(3*n_channels*sizeof(double));
  mp_fit->yt_Nto0 = (double *)malloc(3*n_channels*sizeof(double));

  mp_fit->fit_data = (fitData **)malloc(n_channels*sizeof(fitData*));

  for(i=0;i<NFITTING;i++){
    mp_fit->clamp_start[i] = clamp[i];
  }

  mp_fit->jacobian = (double **)malloc(n_channels*sizeof(double *));
  mp_fit->w_jacobian = (double **)malloc(n_channels*sizeof(double *));
  mp_fit->hessian = (double **)malloc(n_channels*sizeof(double *));
  mp_fit->w_hessian = (double **)malloc(n_channels*sizeof(double *));

  if(independent_heights){
    mp_fit->fn_update = &mpUpdateIndependent;
  }
  else{
    mp_fit->fn_update = &mpUpdateFixed;
  }
    
  return mp_fit;
}


/*
 * mpInitializePSFFFTChannel()
 *
 * Initialize a single channel / plane for 3D PSFFFT fitting.
 */
void mpInitializePSFFFTChannel(mpFit *mp_fit, psfFFT *psf_fft_data, double *variance, int channel)
{
  int jac_size;

  /* Specify how to add new peaks and how to cleanup. */
  if(channel == 0){
    mp_fit->fn_cleanup = &ftFitCleanup;
    mp_fit->fn_newpeaks = &ftFitNewPeaks;
    mp_fit->fn_zrange = &ftFitZRangeCheck;
  }
  
  /*
   * Initialize pupil function fitting for this channel / plane.
   */
  mp_fit->fit_data[channel] = ftFitInitialize(psf_fft_data,
					      variance,
					      mp_fit->clamp_start,
					      mp_fit->tolerance,
					      mp_fit->im_size_x,
					      mp_fit->im_size_y);
  
  /*
   * Allocate storage for jacobian and hessian calculations.
   */
  jac_size = mp_fit->fit_data[channel]->jac_size;
  mp_fit->jacobian[channel] = (double *)malloc(jac_size*sizeof(double));
  mp_fit->w_jacobian[channel] = (double *)malloc(jac_size*sizeof(double));
  mp_fit->hessian[channel] = (double *)malloc(jac_size*jac_size*sizeof(double));
  mp_fit->w_hessian[channel] = (double *)malloc(jac_size*jac_size*sizeof(double));
}


/*
 * mpInitializePupilFnChannel()
 *
 * Initialize a single channel / plane for 3D pupil function fitting.
 */
void mpInitializePupilFnChannel(mpFit *mp_fit, pupilData *pupil_data, double *variance, double zmin, double zmax, int channel)
{
  int jac_size;

  /* Specify how to add new peaks and how to cleanup. */
  if(channel == 0){
    mp_fit->fn_cleanup = &pfitCleanup;
    mp_fit->fn_newpeaks = &pfitNewPeaks;
    mp_fit->fn_zrange = &pfitZRangeCheck;
  }
  
  /*
   * Initialize pupil function fitting for this channel / plane.
   */
  mp_fit->fit_data[channel] = pfitInitialize(pupil_data,
					     variance,
					     mp_fit->clamp_start,
					     mp_fit->tolerance,
					     mp_fit->im_size_x,
					     mp_fit->im_size_y);
  pfitSetZRange(mp_fit->fit_data[channel], zmin, zmax);
  
  /*
   * Allocate storage for jacobian and hessian calculations.
   */
  jac_size = mp_fit->fit_data[channel]->jac_size;
  mp_fit->jacobian[channel] = (double *)malloc(jac_size*sizeof(double));
  mp_fit->w_jacobian[channel] = (double *)malloc(jac_size*sizeof(double));
  mp_fit->hessian[channel] = (double *)malloc(jac_size*jac_size*sizeof(double));
  mp_fit->w_hessian[channel] = (double *)malloc(jac_size*jac_size*sizeof(double));
}


/*
 * mpInitializeSplineChannel()
 *
 * Initialize a single channel / plane for 3D spline fitting.
 */
void mpInitializeSplineChannel(mpFit *mp_fit, splineData *spline_data, double *variance, int channel)
{
  int jac_size;
  
  /* Specify how to add new peaks and how to cleanup. */
  if(channel == 0){
    mp_fit->fn_cleanup = &cfCleanup;
    mp_fit->fn_newpeaks = &cfNewPeaks;
    mp_fit->fn_zrange = &cfZRangeCheck;
  }
  
  /*
   * Initialize spliner fitting for this channel / plane.
   */
  mp_fit->fit_data[channel] = cfInitialize(spline_data,
					   variance,
					   mp_fit->clamp_start,
					   mp_fit->tolerance,
					   mp_fit->im_size_x,
					   mp_fit->im_size_y);
  cfInitialize3D(mp_fit->fit_data[channel]);
  
  /*
   * Allocate storage for jacobian and hessian calculations.
   */
  jac_size = mp_fit->fit_data[channel]->jac_size;
  mp_fit->jacobian[channel] = (double *)malloc(jac_size*sizeof(double));
  mp_fit->w_jacobian[channel] = (double *)malloc(jac_size*sizeof(double));
  mp_fit->hessian[channel] = (double *)malloc(jac_size*jac_size*sizeof(double));
  mp_fit->w_hessian[channel] = (double *)malloc(jac_size*jac_size*sizeof(double));
}


/*
 * mpIterateLM()
 *
 * Perform a single cycle of fitting for each localization using the
 * Levenberg-Marquardt algorithm.
 */
void mpIterateLM(mpFit *mp_fit)
{
  int i,j,k,l,m,n;
  int info,is_bad;
  int n_add;
  double current_error,starting_error;
  fitData *fit_data;

  if(VERBOSE){
    printf("mpILM, nfit = %d\n", mp_fit->nfit);
  }

  for(i=0;i<mp_fit->nfit;i++){
      
    /* Skip ahead if this peak is not RUNNING. */
    if(mp_fit->fit_data[0]->fit[i].status != RUNNING){
      continue;
    }

    if(VERBOSE){
      printf("mpILM index = %d\n", i);
    }
    
    /* 
     * This is for debugging, to make sure that we are adding and 
     * subtracting the right number of times.
     */    
    n_add = mp_fit->n_channels;

    /*
     * Copy peak, calculate jacobian and hessian and subtract.
     */
    starting_error = 0.0;
    for(j=0;j<mp_fit->n_channels;j++){
      fit_data = mp_fit->fit_data[j];
      
      /* Copy current peak into working peak. */
      fit_data->fn_copy_peak(&fit_data->fit[i], fit_data->working_peak);

      /* Calculate current error. */
      mFitCalcErr(fit_data);
      starting_error += fit_data->working_peak->error;
      
      /* Calculate Jacobian and Hessian. This is expected to use 'working_peak'. */
      fit_data->fn_calc_JH(fit_data, mp_fit->jacobian[j], mp_fit->hessian[j]);
    
      /* Subtract current peak out of image. This is expected to use 'working_peak'. */
      fit_data->fn_subtract_peak(fit_data);
      n_add--;
    }
    
    /*
     * Try and improve paired peak parameters.
     */
    j = 0;
    while(1){
      j++;

      if(VERBOSE){
	printf("  cycle %d %d %d\n", i, j, n_add);
      }
      
      is_bad = 0;

      /* 1. Reset status, as it may have changed on a previous pass through this loop. */
      for(k=0;k<mp_fit->n_channels;k++){
	fit_data = mp_fit->fit_data[k];
	fit_data->working_peak->status = RUNNING;
      }
      
      /* 2. Solve for the update vectors. */
      for(k=0;k<mp_fit->n_channels;k++){
	fit_data = mp_fit->fit_data[k];
    
	/* Update total fitting iterations counter. */
	fit_data->n_iterations++;

	/* Copy Jacobian and Hessian. */
	for(l=0;l<fit_data->jac_size;l++){
	  mp_fit->w_jacobian[k][l] = mp_fit->jacobian[k][l];
	  m = l*fit_data->jac_size;
	  for(n=0;n<fit_data->jac_size;n++){
	    if (l == n){
	      mp_fit->w_hessian[k][m+n] = (1.0 + fit_data->working_peak->lambda) * mp_fit->hessian[k][m+n];
	    }
	    else{
	      mp_fit->w_hessian[k][m+n] = mp_fit->hessian[k][m+n];
	    }
	  }
	}
      
	/*  Solve for update. Note that this also changes jacobian. */
	info = mFitSolve(mp_fit->w_hessian[k], mp_fit->w_jacobian[k], fit_data->jac_size);
	
	/* If the solver failed, set is_bad = 1 and exit this loop. */
	if(info!=0){
	  is_bad = 1;
	  fit_data->n_dposv++;
	  if(VERBOSE){
	    printf(" mFitSolve() failed %d %d\n", i, info);
	  }
	  break;
	}
      }

      /* If the solver failed then start over again with a higher lambda for all paired peaks. */
      if(is_bad){
	for(k=0;k<mp_fit->n_channels;k++){
	  fit_data = mp_fit->fit_data[k];
	  fit_data->working_peak->status = ERROR;
	  fit_data->working_peak->lambda = fit_data->working_peak->lambda * LAMBDAUP;
	}
	continue;
      }

      /* 3. Update working peaks. This will use the deltas in w_jacobian. */
      mp_fit->fn_update(mp_fit);
      
      /* 4. Check that the peaks are still in the image, etc.. */
      for(k=0;k<mp_fit->n_channels;k++){
	fit_data = mp_fit->fit_data[k];
	if(fit_data->fn_check(fit_data)){
	  is_bad = 1;
	  if(VERBOSE){
	    printf(" fn_check() failed %d\n", i);
	  }
	}
      }

      /* If the peak parameter check failed start over again with a higher lambda for all paired peaks. */
      if(is_bad){
	mpResetWorkingPeaks(mp_fit, i);
	continue;
      }

      /* 5. Add working peaks back to the fit image. */
      for(k=0;k<mp_fit->n_channels;k++){
	fit_data = mp_fit->fit_data[k];
	fit_data->fn_calc_peak_shape(fit_data);
	fit_data->fn_add_peak(fit_data);
	n_add++;
      }

      /* 6. Calculate updated error. */
      current_error = 0.0;
      for(k=0;k<mp_fit->n_channels;k++){
	fit_data = mp_fit->fit_data[k];
	if(mFitCalcErr(fit_data)){
	  current_error += fit_data->working_peak->error;
	  is_bad = 1;
	  if(VERBOSE){
	    printf(" mFitCalcErr() failed\n");
	  }
	}
      }

      /* If the peak error calculation failed start over again with a higher lambda for all paired peaks. */
      if(is_bad){
	
	/* Undo peak addition. */
	for(k=0;k<mp_fit->n_channels;k++){
	  fit_data = mp_fit->fit_data[k];
	  fit_data->fn_subtract_peak(fit_data);
	  n_add--;
	}
	
	/* Reset working peaks. */
	mpResetWorkingPeaks(mp_fit, i);

	/* Try again. */
	continue;
      }

      /* 7. Check that the error is decreasing. */

      /* If the peak error has increased then start over again with a higher lambda for all paired peaks. */
      if(current_error > starting_error){

	/* 
	 * Check for error convergence. 
	 *
	 * Usually this will happen because the lambda term has gotten so 
	 * large that the peak will barely move in the update.
	 */
      	if (((current_error - starting_error)/starting_error) < mp_fit->tolerance){
	  for(k=0;k<mp_fit->n_channels;k++){
	    mp_fit->fit_data[k]->working_peak->status = CONVERGED;
	  }
	  break;
	}
	else{
	  
	  /* Undo peak addition, and increment counter. */
	  for(k=0;k<mp_fit->n_channels;k++){
	    fit_data = mp_fit->fit_data[k];
	    fit_data->n_non_decr++;
	    fit_data->fn_subtract_peak(fit_data);
	    n_add--;
	  }
	
	  /* Reset working peaks. */
	  mpResetWorkingPeaks(mp_fit, i);

	  /* Try again. */
	  continue;
	}
      }
      else{

	/* Check for error convergence. */
      	if (((starting_error - current_error)/starting_error) < mp_fit->tolerance){
	  for(k=0;k<mp_fit->n_channels;k++){
	    mp_fit->fit_data[k]->working_peak->status = CONVERGED;
	  }
	}

	/* Otherwise reduce lambda. */
	else {
	  for(k=0;k<mp_fit->n_channels;k++){
	    fit_data = mp_fit->fit_data[k];
	    fit_data->working_peak->lambda = fit_data->working_peak->lambda * LAMBDADOWN;
	  }
	}
	break;
      }
    }
	  
    /* We expect n_add to be n_channels if there were no errors, 0 otherwise. */
    if(TESTING){
      if(mp_fit->fit_data[0]->working_peak->status == ERROR){
	if(n_add != 0){
	  printf("Problem detected in peak addition / subtraction logic, status == ERROR, counts = %d\n", n_add);
	  exit(EXIT_FAILURE);
	}
      }
      else{
	if(n_add != mp_fit->n_channels){
	  printf("Problem detected in peak addition / subtraction logic, status != ERROR, counts = %d\n", n_add);
	  exit(EXIT_FAILURE);
	}
      }
    }
    
    /* Copy updated working peak back into current peak. */
    mpCopyFromWorking(mp_fit, i, mp_fit->fit_data[0]->working_peak->status);
  }
}


/*
 * mpIterateOriginal()
 *
 * Perform a single cycle of fitting for each localization using
 * the original 3D-DAOSTORM like algorithm.
 */
void mpIterateOriginal(mpFit *mp_fit)
{
  int i,j;
  int info,is_bad,is_converged;
  fitData *fit_data;

  if(VERBOSE){
    printf("mpIO %d\n", mp_fit->nfit);
  }

  if(!USECLAMP){
    printf("Warning! mpIterateOriginal() without clamping. Mistake?\n");
  }
  
  /*
   * 1. Calculate updated peaks.
   */
  for(i=0;i<mp_fit->nfit;i++){
      
    /* Skip ahead if this peak is not RUNNING. */
    if(mp_fit->fit_data[0]->fit[i].status != RUNNING){
      continue;
    }

    if(VERBOSE){
      printf("mpIO %d\n", i);
    }

    /*
     * Calculate update vector for each channel.
     */
    is_bad = 0;
    for(j=0;j<mp_fit->n_channels;j++){
      fit_data = mp_fit->fit_data[j];
      
      /* Copy current peak into working peak. */
      fit_data->fn_copy_peak(&fit_data->fit[i], fit_data->working_peak);

      /* Calculate Jacobian and Hessian. This is expected to use 'working_peak'. */
      fit_data->fn_calc_JH(fit_data, mp_fit->w_jacobian[j], mp_fit->w_hessian[j]);
    
      /* Subtract current peak out of image. This is expected to use 'working_peak'. */
      fit_data->fn_subtract_peak(fit_data);
    
      /* Update total fitting iterations counter. */
      fit_data->n_iterations++;

      /*  Solve for update. Note that this also changes jacobian. */
      info = mFitSolve(mp_fit->w_hessian[j], mp_fit->w_jacobian[j], fit_data->jac_size);

      /* If the solver failed, set is_bad = 1 and exit this loop. */
      if(info!=0){
	is_bad = 1;
	fit_data->n_dposv++;
	if(VERBOSE){
	  printf(" mFitSolve() failed %d %d\n", i, info);
	}
	break;
      }
    }

    /* 
     * If the solver failed for any peak, mark them all bad and go to
     * the next peak.
     */
    if(is_bad){
      mpCopyFromWorking(mp_fit, i, ERROR);
      continue;
    }

    /* 
     * Update parameters of working peaks. This will use the deltas 
     * in w_jacobian.
     */
    mp_fit->fn_update(mp_fit);

    /* 
     * Check that peaks are still in the image, etc.. The fn_check function
     * should return 0 if everything is okay.
     */    
    for(j=0;j<mp_fit->n_channels;j++){
      fit_data = mp_fit->fit_data[j];
      if(fit_data->fn_check(fit_data)){
	is_bad = 1;
	if(VERBOSE){
	  printf(" fn_check() failed %d\n", i);
	}
      }
    }

    /* 
     * If fn_check() failed for any peak, mark them all bad and go to
     * the next peak.
     */
    if(is_bad){
      mpCopyFromWorking(mp_fit, i, ERROR);
      continue;
    }

    /* Add working peaks back to image and copy back to current peak. */
    for(j=0;j<mp_fit->n_channels;j++){
      fit_data = mp_fit->fit_data[j];
      fit_data->fn_calc_peak_shape(fit_data);
      fit_data->fn_add_peak(fit_data);
      fit_data->fn_copy_peak(fit_data->working_peak, &fit_data->fit[i]);
    }
  }
    
  /*
   * 2. Calculate peak errors.
   */
  for(i=0;i<mp_fit->nfit;i++){
    
    /* Skip ahead if this peak is not RUNNING. */
    if(mp_fit->fit_data[0]->fit[i].status != RUNNING){
      continue;
    }

    /*  Calculate errors for the working peaks. */
    is_bad = 0;
    is_converged = 1;
    for(j=0;j<mp_fit->n_channels;j++){
      fit_data = mp_fit->fit_data[j];
      fit_data->fn_copy_peak(&fit_data->fit[i], fit_data->working_peak);
      if(mFitCalcErr(fit_data)){
	is_bad = 1;
	if(VERBOSE){
	  printf(" mFitCalcErr() failed %d\n", i);
	}
      }
      if(fit_data->working_peak->status != CONVERGED){
	is_converged = 0;
      }
      fit_data->fn_copy_peak(fit_data->working_peak, &fit_data->fit[i]);
    }

    /* If one peak has not converged then mark them all as not converged. */
    if(is_converged != 1){
      for(j=0;j<mp_fit->n_channels;j++){
	mp_fit->fit_data[j]->fit[i].status = RUNNING;
      }
    }

    /* 
     * If one peak has an error, mark them all as error and subtract them
     * out of the fit image.
     */
    if(is_bad){
      for(j=0;j<mp_fit->n_channels;j++){
	fit_data = mp_fit->fit_data[j];

	/* Subtract the peak out of the image. */
	fit_data->fn_copy_peak(&fit_data->fit[i], fit_data->working_peak);
	fit_data->fn_subtract_peak(fit_data);

	/* Set status to ERROR. */
	fit_data->fit[i].status = ERROR;
      }
    }    
  }
}


/*
 * mpNewPeaks()
 *
 * New peaks to fit.
 *
 * n_peaks is the number of peaks per channel.
 */
void mpNewPeaks(mpFit *mp_fit, double *peak_params, char *p_type, int n_peaks)
{
  int i,j,k;
  int is_bad,start,stop;
  double height,tx,ty;
  double *mapped_peak_params;
  fitData *fit_data;
  
  if(VERBOSE){
    printf("mpNP %d\n", n_peaks);
  }

  start = mp_fit->nfit;
  stop = mp_fit->nfit + n_peaks;
  
  if(!strcmp(p_type, "finder") || !strcmp(p_type, "testing")){

    /* We'll use this to pass the mapped peak positions. */
    mapped_peak_params = (double *)malloc(sizeof(double)*n_peaks*3);

    /* Map peak positions & pass to each of the fitters. */
    for(i=0;i<mp_fit->n_channels;i++){
      if(i>0){
	for(j=0;j<n_peaks;j++){
	  k = 3*j;
	  tx = peak_params[k];
	  ty = peak_params[k+1];
	  mapped_peak_params[k] = mp_fit->yt_0toN[i*3] + ty*mp_fit->yt_0toN[i*3+1] + tx*mp_fit->yt_0toN[i*3+2];
	  mapped_peak_params[k+1] = mp_fit->xt_0toN[i*3] + ty*mp_fit->xt_0toN[i*3+1] + tx*mp_fit->xt_0toN[i*3+2];
	  mapped_peak_params[k+2] = peak_params[k+2];
	}
	mp_fit->fn_newpeaks(mp_fit->fit_data[i], mapped_peak_params, p_type, n_peaks);
      }
      else{
	mp_fit->fn_newpeaks(mp_fit->fit_data[i], peak_params, p_type, n_peaks);
      }
    }

    /* Correct heights and errors when peaks are not independent. */
    if(!mp_fit->independent_heights){
      for(i=start;i<stop;i++){

	/* 
	 * Copy current peaks into working peaks and calculate
	 * average height.
	 */
	height = 0.0;
	for(j=0;j<mp_fit->n_channels;j++){
	  fit_data = mp_fit->fit_data[j];
	  fit_data->fn_copy_peak(&fit_data->fit[i], fit_data->working_peak);
	  height += fit_data->working_peak->params[HEIGHT];
	}
	height = height/((double)mp_fit->n_channels);

	/* Subtract current peaks from the image. */
	for(j=0;j<mp_fit->n_channels;j++){
	  fit_data = mp_fit->fit_data[j];
	  if(fit_data->working_peak->status != ERROR){
	    fit_data->fn_subtract_peak(fit_data);
	  }
	}
	
	/* 
	 * Set all peaks to have the same height, add back into 
	 * fit image, calculate their error & copy back from 
	 * the working peak.
	 */
	for(j=0;j<mp_fit->n_channels;j++){
	  fit_data = mp_fit->fit_data[j];
	  fit_data->working_peak->params[HEIGHT] = height;
	  if(fit_data->working_peak->status != ERROR){
	    fit_data->fn_add_peak(fit_data);
	    mFitCalcErr(fit_data);	    
	  }
	  fit_data->fn_copy_peak(fit_data->working_peak, &fit_data->fit[i]);
	}
      }
    }

    free(mapped_peak_params);
  }
  else{
    mapped_peak_params = (double *)malloc(sizeof(double)*n_peaks*5);

    /* Map peak positions & pass to each of the fitters. */
    for(i=0;i<mp_fit->n_channels;i++){
      if(i>0){
	for(j=0;j<n_peaks;j++){
	  k = 5*j;
	  tx = peak_params[k];
	  ty = peak_params[k+1];
	  mapped_peak_params[k] = mp_fit->yt_0toN[i*3] + ty*mp_fit->yt_0toN[i*3+1] + tx*mp_fit->yt_0toN[i*3+2];
	  mapped_peak_params[k+1] = mp_fit->xt_0toN[i*3] + ty*mp_fit->xt_0toN[i*3+1] + tx*mp_fit->xt_0toN[i*3+2];
	  mapped_peak_params[k+2] = peak_params[k+2];
	  mapped_peak_params[k+3] = peak_params[k+3];
	  mapped_peak_params[k+4] = peak_params[k+4];
	}
	mp_fit->fn_newpeaks(mp_fit->fit_data[i], mapped_peak_params, p_type, n_peaks);
      }
      else{
	mp_fit->fn_newpeaks(mp_fit->fit_data[i], peak_params, p_type, n_peaks);
      }
    }
    
    free(mapped_peak_params);
  }

  /* 
   * Check for error peaks & synchronize status. This can happen for example
   * because the peak in one channel is outside the image.
   */
  for(i=start;i<stop;i++){
    is_bad = 0;
    for(j=0;j<mp_fit->n_channels;j++){
      if(mp_fit->fit_data[j]->fit[i].status == ERROR){
	is_bad = 1;
	break;
      }
    }
    
    if(is_bad){
      for(j=0;j<mp_fit->n_channels;j++){

	/* Check if we need to subtract this peak out of the image. */
	if(mp_fit->fit_data[j]->fit[i].status != ERROR){
	  fit_data = mp_fit->fit_data[j];
	  fit_data->fn_copy_peak(&fit_data->fit[i], fit_data->working_peak);
	  fit_data->fn_subtract_peak(fit_data);
	}
	mp_fit->fit_data[j]->fit[i].status = ERROR;
      }
    }
  }

  mp_fit->nfit = stop;
}


/*
 * mpResetWorkingPeaks()
 *
 * Restore working peaks to their original state, but with larger lambda
 * and status ERROR. This is used by mpIterateLM().
 */
void mpResetWorkingPeaks(mpFit *mp_fit, int index)
{
  int i,tmp_added;
  double tmp_lambda;
  fitData *fit_data;
  
  for(i=0;i<mp_fit->n_channels;i++){
    fit_data = mp_fit->fit_data[i];
    
    /* Reset peak (it was changed by fn_update()), increase lambda. */
    tmp_added = fit_data->working_peak->added;
    tmp_lambda = fit_data->working_peak->lambda;
    fit_data->fn_copy_peak(&fit_data->fit[index], fit_data->working_peak);
    fit_data->working_peak->added = tmp_added;
    fit_data->working_peak->lambda = tmp_lambda * LAMBDAUP;

    /* Set status to ERROR in case this is the last iteration. */
    fit_data->working_peak->status = ERROR;
  }
}


/*
 * mpSetTransforms()
 *
 * Set affine transform arrays that describe how to change
 * the coordinates between channels. 
 *
 * These are expected to be by channel, then by coefficient.
 */
void mpSetTransforms(mpFit *mp_fit, double *xt_0toN, double *yt_0toN, double *xt_Nto0, double *yt_Nto0)
{
  int i,m;

  m = mp_fit->n_channels*3;
  
  for(i=0;i<m;i++){
    mp_fit->xt_0toN[i] = xt_0toN[i];
    mp_fit->yt_0toN[i] = yt_0toN[i];
    mp_fit->xt_Nto0[i] = xt_Nto0[i];
    mp_fit->yt_Nto0[i] = yt_Nto0[i];
  }
}


/*
 * mpSetWeights()
 *
 * Set values to use when averaging the per-channel updates. For
 * now the background parameter is independent for each channel,
 * though this may change, so we set it anyway.
 *
 * These are expected to be indexed by z, then channel, so the z
 * value is the slow axis and the channel is the fast axis.
 */
void mpSetWeights(mpFit *mp_fit, double *w_bg, double *w_h, double *w_x, double *w_y, double *w_z, int z_size)
{
  int i,n;

  printf("Weight z size %d\n", z_size);
  
  mp_fit->n_weights = z_size;
  
  /* Allocate storage. */
  n = mp_fit->n_channels*z_size;
  mp_fit->w_bg = (double *)malloc(sizeof(double)*n);
  mp_fit->w_h = (double *)malloc(sizeof(double)*n);
  mp_fit->w_x = (double *)malloc(sizeof(double)*n);
  mp_fit->w_y = (double *)malloc(sizeof(double)*n);
  mp_fit->w_z = (double *)malloc(sizeof(double)*n);
  mp_fit->heights = (double *)malloc(sizeof(double)*mp_fit->n_channels);
  
  /* Copy values. */
  for(i=0;i<n;i++){
    mp_fit->w_bg[i] = w_bg[i];
    mp_fit->w_h[i] = w_h[i];
    mp_fit->w_x[i] = w_x[i];
    mp_fit->w_y[i] = w_y[i];
    mp_fit->w_z[i] = w_z[i];
  }

  /* Set initial height weighting values to 1.0 for fixed (relative) height fitting. */
  for(i=0;i<mp_fit->n_channels;i++){
    mp_fit->heights[i] = 1.0;
  }
}

/*
 * mpSetWeightsIndexing()
 *
 * Set the values to use for conversion of a peak Z position to 
 * an index into the weights arrays.
 */
void mpSetWeightsIndexing(mpFit *mp_fit, double z_offset, double z_scale)
{
  mp_fit->w_z_offset = z_offset;
  mp_fit->w_z_scale = z_scale;
}

/*
 * mpUpdate()
 *
 * Calculate weighted delta and update each channel.
 *
 * mp_fit->heights should be all 1.0 for fixed (relative) heights.
 *
 * Note: This assumes that the fitting library is using the 
 *       following convention:
 *
 *  delta[0] = HEIGHT;
 *  delta[1] = XCENTER;
 *  delta[2] = YCENTER;
 *  delta[3] = ZCENTER;
 *  delta[4] = BACKGROUND;
 */
void mpUpdate(mpFit *mp_fit)
{
  int i,nc,zi;
  double delta,p_ave,p_total,t,xoff,yoff;
  double *params_ch0,*heights;
  peakData *peak;
  fitData *fit_data_ch0;

  heights = mp_fit->heights;
  fit_data_ch0 = mp_fit->fit_data[0];
  params_ch0 = fit_data_ch0->working_peak->params;
  xoff = fit_data_ch0->xoff;
  yoff = fit_data_ch0->yoff;
  
  nc = mp_fit->n_channels;

  /* 
   * Calculate index into z-dependent weight values and do some range
   * checking.
   */
  zi = (int)(mp_fit->w_z_scale * (params_ch0[ZCENTER] - mp_fit->w_z_offset));
  if(zi<0){
    if(TESTING){
      printf("Negative weight index detected %d\n", zi);
    }
    zi = 0;
  }
  if(zi>=mp_fit->n_weights){
    if(TESTING){
      printf("Out of range weight index detected %d\n", zi);
    }
    zi = mp_fit->n_weights-1;
  }
  if(VERBOSE){
    printf("zi is %d for peak %d\n", zi, fit_data_ch0->working_peak->index);
  }
  
  /*
   * X parameters depends on the mapping.
   *
   * Note: The meaning of x and y is transposed here compared to in the
   *       mapping. This is also true for the y parameter below.
   */
  p_ave = 0.0;
  p_total = 0.0;
  for(i=0;i<nc;i++){
    if(VERBOSE){
      printf(" x %d %.3e %.3e", i, heights[i], mp_fit->yt_Nto0[i*3+1]);
      printf(" %.3e %.3e %.3e\n", mp_fit->w_jacobian[i][2], mp_fit->yt_Nto0[i*3+2], mp_fit->w_jacobian[i][1]);
    }
    delta = mp_fit->yt_Nto0[i*3+1] * mp_fit->w_jacobian[i][2];
    delta += mp_fit->yt_Nto0[i*3+2] * mp_fit->w_jacobian[i][1];
    p_ave += delta * mp_fit->w_x[zi*nc+i] * heights[i];
    p_total += mp_fit->w_x[zi*nc+i] * heights[i];
  }
  delta = p_ave/p_total;
  mFitUpdateParam(fit_data_ch0->working_peak, delta, XCENTER);

  /* Y parameters also depend on the mapping. */
  p_ave = 0.0;
  p_total = 0.0;
  for(i=0;i<nc;i++){
    if(VERBOSE){
      printf(" y %d %.3e %.3e", i, heights[i], mp_fit->xt_Nto0[i*3+1]);
      printf(" %.3e %.3e %.3e\n", mp_fit->w_jacobian[i][2], mp_fit->xt_Nto0[i*3+2], mp_fit->w_jacobian[i][1]);
    }
    delta = mp_fit->xt_Nto0[i*3+1] * mp_fit->w_jacobian[i][2];
    delta += mp_fit->xt_Nto0[i*3+2] * mp_fit->w_jacobian[i][1];
    p_ave += delta * mp_fit->w_y[zi*nc+i] * heights[i];
    p_total += mp_fit->w_y[zi*nc+i] * heights[i];
  }
  delta = p_ave/p_total;
  mFitUpdateParam(fit_data_ch0->working_peak, delta, YCENTER);  

  /* 
   * Use mapping to update peak locations in the remaining channels.
   * 
   * Note: The meaning of x and y is transposed here compared to in the
   *       mapping.
   *
   * Note: Spliner uses the upper left corner as 0,0 so we need to adjust
   *       to the center, transform, then adjust back. This is particularly
   *       important if one channel is inverted relative to another.
   */
  for(i=1;i<nc;i++){
    peak = mp_fit->fit_data[i]->working_peak;
    
    t = mp_fit->yt_0toN[i*3];
    t += mp_fit->yt_0toN[i*3+1] * (params_ch0[YCENTER]+yoff);
    t += mp_fit->yt_0toN[i*3+2] * (params_ch0[XCENTER]+xoff);
    peak->params[XCENTER] = t-xoff;

    t = mp_fit->xt_0toN[i*3];
    t += mp_fit->xt_0toN[i*3+1] * (params_ch0[YCENTER]+yoff);
    t += mp_fit->xt_0toN[i*3+2] * (params_ch0[XCENTER]+xoff);
    peak->params[YCENTER] = t-yoff;
  }

  /* Update peak (integer) location with hysteresis. */
  for(i=0;i<nc;i++){
    peak = mp_fit->fit_data[i]->working_peak;
    if(fabs(peak->params[XCENTER] - (double)peak->xi) > HYSTERESIS){
      peak->xi = (int)round(peak->params[XCENTER]);
    }
    if(fabs(peak->params[YCENTER] - (double)peak->yi) > HYSTERESIS){
      peak->yi = (int)round(peak->params[YCENTER]);
    }
  }

  /* Z parameter is a simple weighted average. */
  p_ave = 0.0;
  p_total = 0.0;
  for(i=0;i<nc;i++){
    p_ave += mp_fit->w_jacobian[i][3] * mp_fit->w_z[zi*nc+i] * heights[i];
    p_total += mp_fit->w_z[zi*nc+i] * heights[i];
  }
  delta = p_ave/p_total;

  for(i=0;i<nc;i++){
    peak = mp_fit->fit_data[i]->working_peak;
    mFitUpdateParam(peak, delta, ZCENTER);
    
    /* Force z value to stay in range. */
    mp_fit->fn_zrange(mp_fit->fit_data[i]);
  }

  /* Backgrounds float independently. */
  for(i=0;i<nc;i++){
    mFitUpdateParam(mp_fit->fit_data[i]->working_peak, mp_fit->w_jacobian[i][4], BACKGROUND);
  }
}


/*
 * mpUpdateFixed()
 *
 * Calculate weighted delta and update each channel for fitting
 * with peak heights fixed relative to each other. This does not
 * change mp_fit->heights;
 *
 * Note: This allows negative heights, which will get removed by fn_check().
 *
 * Note: This assumes that the fitting library is using the 
 *       following convention:
 *
 *  delta[0] = HEIGHT;
 *  delta[1] = XCENTER;
 *  delta[2] = YCENTER;
 *  delta[3] = ZCENTER;
 *  delta[4] = BACKGROUND;
 */
void mpUpdateFixed(mpFit *mp_fit)
{
  int i,nc,zi;
  double delta, p_ave, p_total;
  fitData *fit_data_ch0;

  fit_data_ch0 = mp_fit->fit_data[0];
  nc = mp_fit->n_channels;

  zi = (int)(mp_fit->w_z_scale * (fit_data_ch0->working_peak->params[ZCENTER] - mp_fit->w_z_offset));
  if(zi<0){
    if(TESTING){
      printf("Negative weight index detected %d\n", zi);
      exit(EXIT_FAILURE);
    }
    zi = 0;
  }
  if(zi>=mp_fit->n_weights){
    if(TESTING){
      printf("Out of range weight index detected %d\n", zi);
      exit(EXIT_FAILURE);
    }
    zi = mp_fit->n_weights-1;
  }

  /* Height, this is a simple weighted average. */
  p_ave = 0.0;
  p_total = 0.0;
  for(i=0;i<nc;i++){
    if(VERBOSE){
      printf(" h %d %.3e\n", i, mp_fit->w_jacobian[i][0]);
    }
    p_ave += mp_fit->w_jacobian[i][0] * mp_fit->w_h[zi*nc+i];
    p_total += mp_fit->w_h[zi*nc+i];
  }
  delta = p_ave/p_total;
  
  mFitUpdateParam(fit_data_ch0->working_peak, delta, HEIGHT);
  for(i=1;i<nc;i++){
    mp_fit->fit_data[i]->working_peak->params[HEIGHT] = fit_data_ch0->working_peak->params[HEIGHT];
  }

  mpUpdate(mp_fit);
}


/*
 * mpUpdateIndependent()
 *
 * Calculate weighted delta and update each channel for fitting
 * with independently adjustable peak heights.
 *
 * Note: This assumes that the PSF fitting library is using the 
 *       following convention:
 *
 *  delta[0] = HEIGHT;
 *  delta[1] = XCENTER;
 *  delta[2] = YCENTER;
 *  delta[3] = ZCENTER;
 *  delta[4] = BACKGROUND;
 */
void mpUpdateIndependent(mpFit *mp_fit)
{
  int i,nc;
  peakData *peak;

  nc = mp_fit->n_channels;
  for(i=0;i<nc;i++){
    peak = mp_fit->fit_data[i]->working_peak;
    mFitUpdateParam(peak, mp_fit->w_jacobian[i][0], HEIGHT);

    /* Prevent small/negative peak heights. */
    if(peak->params[HEIGHT] < 0.01){
      peak->params[HEIGHT] = 0.01;
    }
    
    mp_fit->heights[i] = peak->params[HEIGHT];
  }

  mpUpdate(mp_fit);
}

