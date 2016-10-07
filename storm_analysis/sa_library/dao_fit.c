/*
 * Routine(s) for attempting to (MLE) fit multiple gaussians to an image.
 * The approach follows Laurence and Chromy, Nature Methods, 2010.
 *
 * 01/11
 *
 *
 * Generalized for 2D & 3D fitting.
 *
 * 07/11
 *
 *
 * Speed things up by only updating foreground and background data
 * for those peaks that are still running (i.e. moving around).
 *
 * 10/11
 *
 *
 * Remove (useless) OFFSET term.
 *
 * 03/13
 *
 *
 * Add hystersis to minimize a bad interaction between the parameter
 * clamp and moving / changing the size of the AOI.
 *
 * 07/13
 *
 *
 * Add scmos_term to enable analysis of sCMOS data.
 *
 * 10/13
 *
 *
 * Remove static variables so that it is thread safe.
 *
 * 09/16
 *
 * Hazen
 * 
 * Compilation instructions:
 *
 * Linux:
 *  gcc -fPIC -g -c -Wall multi_fit.c
 *  gcc -shared -Wl,-soname,multi_fit.so.1 -o multi_fit.so.1.0.1 multi_fit.o -lc -llapack
 *
 * Windows:
 *  gcc -c multi_fit.c
 *  gcc -shared -o multi_fit.dll multi_fit.o -llapack -Lc:\Users\Hazen\lib
 */

/* Include */
#include <stdlib.h>
#include <stdio.h>
#include <math.h>

#include "multi_fit.h"

/* Define */

#define HYSTERESIS 0.6 /* In order to move the AOI or change it's size,
			  the new value must differ from the old value
			  by at least this much (<= 0.5 is no hysteresis). */

#define MARGIN 10      /* Margin around the edge of the image. This
			  also sets the maximum number of pixels that will
			  be fit.
			  
			  FIXME: This should be adjustable. */


/* Structures */
typedef struct
{
  double wx_term;
  double wy_term;
  
  double xt[2*MARGIN+1];
  double ext[2*MARGIN+1];
  double yt[2*MARGIN+1];
  double eyt[2*MARGIN+1];
} daoPeak;

typedef struct
{
  int zfit;                 /* fit with wx, wy as fixed functions of z. */

  double wx_z_params[5];        /* x width versus z parameters. */
  double wy_z_params[5];        /* y width versus z parameters. */
} daoFit;


/* Function Declarations */
void addPeak(fitData *, peakData *);
int calcWidth(double, int);
void calcWidthsFromZ(fitData *, peakData *);
void cleanup(fitData *);
void fitDataUpdate(fitData *, peakData *, double *);
fitData* initialize(double *, double *, double, int, int);
void initializeZParameters(fitData *, double *, double *, double, double);
void iterate2DFixed(fitData *);
void iterate2D(fitData *);
void iterate3D(fitData *);
void iterateZ(fitData *);
void newPeaks(fitData *, double *, int);
void subtractPeak(fitData *, peakData *);
void update2DFixed(fitData *, peakData *);
void update2D(fitData *, peakData *);
void update3D(fitData *, peakData *);
void updateZ(fitData *, peakData *);


/* LAPACK Functions */
extern void dposv_(char* uplo, int* n, int* nrhs, double* a, int* lda,
		   double* b, int* ldb, int* info);


/*
 * addPeak()
 *
 * Add a peak to the foreground and background data arrays.
 *
 * fit_data - pointer to a fitData structure.
 * peak - pointer to a peakData structure.
 */
void addPeak(fitData *fit_data, peakData *peak)
{
  int j,k,l,m,n,wx,wy,xc,yc;
  double bg,mag,tmp,xt,yt;
  daoPeak *dao_peak;

  dao_peak = (daoPeak *)peak->peakModel;

  xc = peak->xc;
  yc = peak->yc;
  peak->offset = yc * fit_data->image_size_x + xc;

  wx = peak->wx;
  wy = peak->wy;

  for(j=(xc-wx);j<=(xc+wx);j++){
    xt = (double)j - peak->params[XCENTER];
    n = j-xc+wx;
    dao_peak->xt[n] = xt;
    dao_peak->ext[n] = exp(-xt*xt*peak->params[XWIDTH]);
  }
  for(j=(yc-wy);j<=(yc+wy);j++){
    yt = (double)j - peak->params[YCENTER];
    n = j-yc+wy;
    dao_peak->yt[n] = yt;
    dao_peak->eyt[n] = exp(-yt*yt*peak->params[YWIDTH]);
  }

  /* gaussian function */
  l = peak->offset;
  bg = peak->params[BACKGROUND];
  mag = peak->params[HEIGHT];
  for(j=-wy;j<=wy;j++){
    tmp = dao_peak->eyt[j+wy];
    for(k=-wx;k<=wx;k++){
      m = j * fit_data->image_size_x + k + l;
      fit_data->f_data[m] += mag * tmp * dao_peak->ext[k+wx];
      fit_data->bg_counts[m] += 1;
      fit_data->bg_data[m] += bg + fit_data->scmos_term[m];
    }
  }
}


/*
 * calcWidth(peak_width)
 *
 * Given a peak_width, returns the appropriate 
 * bounding box to use for fitting.
 */
int calcWidth(double peak_width, int old_w)
{
  int new_w;
  double tmp;

  if(peak_width < 0.0){
    if(TESTING){
      printf(" Got negative peak width! %.3f", peak_width);
    }
    return 1;
  }
  else{
    new_w = old_w;
    tmp = 4.0*sqrt(1.0/(2.0*peak_width));
    if(fabs(tmp - (double)old_w - 0.5) > HYSTERESIS){
      new_w = (int)tmp;
    }
    if(new_w > MARGIN){
      new_w = MARGIN;
    }
    return new_w;
  }
}


/*
 * calcWidthsFromZ(cur)
 *
 * Updates wx, wy given z.
 *
 * fit_data - The fitD
 * peak - Peak data structure to update.
 */
void calcWidthsFromZ(fitData *fit_data, peakData *peak)
{
  double z0,z1,z2,z3,tmp;
  daoFit *dao_fit;
  daoPeak *dao_peak;

  dao_fit = (daoFit *)fit_data->fitModel;
  dao_peak = (daoPeak *)peak->peakModel;

  // wx
  z0 = (peak->params[ZCENTER] - dao_fit->wx_z_params[1]) / dao_fit->wx_z_params[2];
  z1 = z0*z0;
  z2 = z1*z0;
  z3 = z2*z0;
  tmp = 1.0 + z1 + dao_fit->wx_z_params[3] * z2 + dao_fit->wx_z_params[4] * z3;
  dao_peak->wx_term = tmp*tmp;
  peak->params[XWIDTH] = 2.0/(dao_fit->wx_z_params[0] * tmp);

  // wy
  z0 = (peak->params[ZCENTER] - dao_fit->wy_z_params[1]) / dao_fit->wy_z_params[2];
  z1 = z0*z0;
  z2 = z1*z0;
  z3 = z2*z0;
  tmp = 1.0 + z1 + dao_fit->wy_z_params[3] * z2 + dao_fit->wy_z_params[4] * z3;
  dao_peak->wy_term = tmp*tmp;
  peak->params[YWIDTH] = 2.0/(dao_fit->wy_z_params[0] * tmp);
}


/*
 * cleanup()
 *
 * Frees the fitData structure.
 *
 * fit_data - pointer to a fitData structure.
 */
void cleanup(fitData *fit_data)
{
  int i;

  if(fit_data->fit != NULL){
    for(i=0;i<fit_data->nfit;i++){
      free((daoPeak *)fit_data->fit[i].peakModel);
    }
    free(fit_data->fit);
  }
  free((daoFit *)fit_data->fitModel);
  free(fit_data->bg_counts);
  free(fit_data->bg_data);
  free(fit_data->f_data);
  free(fit_data->scmos_term);
  free(fit_data->x_data);
  free(fit_data);
}


/*
 * fitDataUpdate()
 *
 * Updates fit data given deltas.
 *
 * Also checks for out-of-bounds parameters.
 *
 * fit_data - pointer to a fitData structure.
 * peak - pointer to the peakData structure to update.
 * delta - the deltas for different parameters.
 */
void fitDataUpdate(fitData *fit_data, peakData *peak, double *delta)
{
  int xc,yc;

  // update
  updateParams(peak, delta);

  // Update peak (integer) center (w/ hysteresis).
  if(fabs(peak->params[XCENTER] - (double)peak->xc - 0.5) > HYSTERESIS){
    peak->xc = (int)peak->params[XCENTER];
  }
  if(fabs(peak->params[YCENTER] - (double)peak->yc - 0.5) > HYSTERESIS){
    peak->yc = (int)peak->params[YCENTER];
  }

  // Check that the peak hasn't moved to close to the 
  // edge of the image. Flag the peak as bad if it has.
  xc = peak->xc;
  yc = peak->yc;
  if((xc <= MARGIN)||(xc >= (fit_data->image_size_x - MARGIN-1))||(yc <= MARGIN)||(yc >= (fit_data->image_size_y - MARGIN - 1))){
    peak->status = ERROR;
    fit_data->n_margin++;
    if(TESTING){
      printf("object outside margins, %.3f, %.3f\n", peak->params[XCENTER], peak->params[YCENTER]);
    }
  }
  
  // check for negative background or height
  if(peak->params[HEIGHT]<0.0){
    peak->status = ERROR;
    fit_data->n_neg_height++;
    if(TESTING){
      printf("negative height, %.3f, %.3f (%.3f, %.3f)\n", peak->params[BACKGROUND], peak->params[HEIGHT], peak->params[XCENTER], peak->params[YCENTER]);
    }
  }

  // check for negative widths
  if((peak->params[XWIDTH]<0.0)||(peak->params[YWIDTH]<0.0)){
    peak->status = ERROR;
    fit_data->n_neg_width++;
    if(TESTING){
      printf("negative widths, %.3f, %.3f (%.3f, %.3f)\n", peak->params[XWIDTH], peak->params[YWIDTH], peak->params[XCENTER], peak->params[YCENTER]);
    }
  }

  // Option 1: Peak errors out if z is out of range.
  /*
  if((cur->params[ZCENTER]<MINZ)||(cur->params[ZCENTER]>MAXZ)){
    cur->status = ERROR;
    if(TESTING){
      printf("z value out of range, %.3f (%.3f, %.3f)\n", cur->params[ZCENTER], cur->params[XCENTER], cur->params[YCENTER]);
    }
  }
  */

  // Option 2: Clamp z value range.
  if (((daoFit *)fit_data->fitModel)->zfit){
    if(peak->params[ZCENTER] < fit_data->min_z){
      peak->params[ZCENTER] = fit_data->min_z;
    }

    if(peak->params[ZCENTER] > fit_data->max_z){
      peak->params[ZCENTER] = fit_data->max_z;
    }
  }

}


/*
 * initialize(image, params, tol, im_size, n)
 *
 * Initializes fitting things for fitting.
 *
 * scmos_calibration - sCMOS calibration data, variance/gain^2 for each pixel in the image.
 * clamp - The starting clamp values for each peak.
 * tol - The fitting tolerance.
 * im_size_x - size of the image in x.
 * im_size_y - size of the image in y.
 *
 * Returns - Pointer to the fitdata structure.
 */
fitData* initialize(double *scmos_calibration, double *clamp, double tol, int im_size_x, int im_size_y)
{
  int i;
  fitData* fit_data;

  /* Initialize fitData structure. */
  fit_data = (fitData*)malloc(sizeof(fitData));
  fit_data->image_size_x = im_size_x;
  fit_data->image_size_y = im_size_y;
  fit_data->tolerance = tol;
  fit_data->fit = NULL;

  fit_data->fitModel = (daoFit *)malloc(sizeof(daoFit));
  ((daoFit *)fit_data->fitModel)->zfit = 0;
  
  /* Copy sCMOS calibration data. */
  fit_data->scmos_term = (double *)malloc(sizeof(double)*im_size_x*im_size_y);
  for(i=0;i<(im_size_x*im_size_y);i++){
    fit_data->scmos_term[i] = scmos_calibration[i];
  }

  /* Copy starting clamp values. */
  for(i=0;i<7;i++){
    fit_data->clamp_start[i] = clamp[i];
  }

  /* Allocate space for image, fit and background arrays. */
  fit_data->bg_counts = (int *)malloc(sizeof(int)*im_size_x*im_size_y);
  fit_data->bg_data = (double *)malloc(sizeof(double)*im_size_x*im_size_y);
  fit_data->f_data = (double *)malloc(sizeof(double)*im_size_x*im_size_y);
  fit_data->x_data = (double *)malloc(sizeof(double)*im_size_x*im_size_y);

  /* 
   * Default z fitting range. This is only relevant for Z mode peak 
   * fitting. These values are set to the correct values by calling
   * initializeZParameters().
   */
  fit_data->min_z = -1.0e-6;
  fit_data->max_z = 1.0e+6;

  return fit_data;
}

/*
 * initializeZParameters(wx_vs_z, wy_vs_z)
 *
 * Initializes fitting for z with wx, wy dependence on z.
 *
 * fit_data - pointer to a fitData structure.
 * wx_vs_z - [wo, c, d, A, B] wx vs z coefficients.
 * wy_vs_z - [wo, c, d, A, B] wy vs z coefficients.
 * z_min - minimum allowed z value.
 * z_max - maximum allowed z value.
 */
void initializeZParameters(fitData* fit_data, double *wx_vs_z, double *wy_vs_z, double z_min, double z_max)
{
  int i;
  daoFit *dao_fit;

  dao_fit = (daoFit *)fit_data->fitModel;

  dao_fit->zfit = 1;
  for(i=0;i<5;i++){
    dao_fit->wx_z_params[i] = wx_vs_z[i];
    dao_fit->wy_z_params[i] = wy_vs_z[i];
  }
  dao_fit->wx_z_params[0] = dao_fit->wx_z_params[0] * dao_fit->wx_z_params[0];
  dao_fit->wy_z_params[0] = dao_fit->wy_z_params[0] * dao_fit->wy_z_params[0];

  fit_data->min_z = z_min;
  fit_data->max_z = z_max;
}


/*
 * iterate2DFixed()
 *
 * Performs a single cycle of fit improvement with fixed x, y width.
 *
 */
void iterate2DFixed(fitData *fit_data)
{
  int i;
  peakData *peak;

  /*
   * Why so complicated? 
   *
   * The ultimate goal is too further reduce the code redundancy in 
   * dao vs spline fitting. As an initial step we are trying to harmonize
   * the signatures of the functions that serve the same purpose.
   */
  for(i=0;i<fit_data->nfit;i++){
    peak = &fit_data->fit[i];
    update2DFixed(fit_data, peak);
  }
  
  for(i=0;i<fit_data->nfit;i++){
    peak = &fit_data->fit[i];
    calcErr(fit_data, peak);
  }
}


/*
 * iterate2D()
 *
 * Performs a single cycle of fit improvement with equal x, y width.
 *
 */
void iterate2D(fitData *fit_data)
{
  int i;
  peakData *peak;

  for(i=0;i<fit_data->nfit;i++){
    peak = &fit_data->fit[i];
    update2D(fit_data, peak);
  }
  
  for(i=0;i<fit_data->nfit;i++){
    peak = &fit_data->fit[i];
    calcErr(fit_data, peak);
  }
}


/*
 * iterate3D()
 *
 * Performs a single cycle of fit improvement.
 */
void iterate3D(fitData *fit_data)
{
  int i;
  peakData *peak;

  for(i=0;i<fit_data->nfit;i++){
    peak = &fit_data->fit[i];
    update3D(fit_data, peak);
  }
  
  for(i=0;i<fit_data->nfit;i++){
    peak = &fit_data->fit[i];
    calcErr(fit_data, peak);
  }
}


/*
 * iterateZ()
 *
 * Performs a single cycle of fit improvement with x, y width
 * determined by the z parameter.
 */
void iterateZ(fitData *fit_data)
{
  int i;
  peakData *peak;

  for(i=0;i<fit_data->nfit;i++){
    peak = &fit_data->fit[i];
    updateZ(fit_data, peak);
  }

  for(i=0;i<fit_data->nfit;i++){
    peak = &fit_data->fit[i];
    calcErr(fit_data, peak);
  }
}


/*
 * newPeaks
 *
 * fit_data - Pointer to a fitData structure.
 * peak_data - Input values for the peak parameters.
 * n_peaks - The number of peaks.
 */
void newPeaks(fitData *fit_data, double *peak_data, int n_peaks)
{
  int i,j;
  peakData *peak;

  /*
   * Reset diagnostics.
   */
  fit_data->n_dposv = 0;
  fit_data->n_margin = 0;
  fit_data->n_neg_fi = 0;
  fit_data->n_neg_height = 0;
  fit_data->n_neg_width = 0;
 
  /*
   * Reset fitting arrays.
   */
  for(i=0;i<(fit_data->image_size_x*fit_data->image_size_y);i++){
    fit_data->bg_counts[i] = 0;
    fit_data->bg_data[i] = 0.0;
    fit_data->f_data[i] = 0.0;
  }

  /*
   * Free old peaks, if necessary.
   */
  if(fit_data->fit != NULL){
    for(i=0;i<fit_data->nfit;i++){
      free((daoPeak *)fit_data->fit[i].peakModel);
    }
    free(fit_data->fit);
  }

  /*
   * Initialize peaks (localizations).
   */
  fit_data->nfit = n_peaks;
  fit_data->fit = (peakData *)malloc(sizeof(peakData)*n_peaks);
  for(i=0;i<fit_data->nfit;i++){
    peak = &fit_data->fit[i];
    peak->peakModel = (daoPeak *)malloc(sizeof(daoPeak));
    
    peak->status = (int)(peak_data[i*NPEAKPAR+STATUS]);
    if(peak->status==RUNNING){
      peak->error = 0.0;
      peak->error_old = 0.0;
    }
    else {
      peak->error = peak_data[i*NPEAKPAR+IERROR];
      peak->error_old = peak->error;
    }
    
    peak->params[HEIGHT]     = peak_data[i*NPEAKPAR+HEIGHT];
    peak->params[XCENTER]    = peak_data[i*NPEAKPAR+XCENTER];
    peak->params[YCENTER]    = peak_data[i*NPEAKPAR+YCENTER];
    peak->params[BACKGROUND] = peak_data[i*NPEAKPAR+BACKGROUND];
    peak->params[ZCENTER]    = peak_data[i*NPEAKPAR+ZCENTER];

    if(((daoFit *)fit_data->fitModel)->zfit){
      calcWidthsFromZ(fit_data, peak);
    }
    else{
      peak->params[XWIDTH] = 1.0/(2.0*peak_data[i*NPEAKPAR+XWIDTH]*peak_data[i*NPEAKPAR+XWIDTH]);
      peak->params[YWIDTH] = 1.0/(2.0*peak_data[i*NPEAKPAR+YWIDTH]*peak_data[i*NPEAKPAR+YWIDTH]);
    }

    peak->xc = (int)peak->params[XCENTER];
    peak->yc = (int)peak->params[YCENTER];
    peak->wx = calcWidth(peak->params[XWIDTH],-10.0);
    peak->wy = calcWidth(peak->params[YWIDTH],-10.0);

    for(j=0;j<NFITTING;j++){
      peak->clamp[j] = fit_data->clamp_start[j];
      peak->sign[j] = 0;
    }

    addPeak(fit_data, peak);
  }

  /* Initial error calculation. */
  for(i=0;i<fit_data->nfit;i++){
    calcErr(fit_data, &fit_data->fit[i]);
  }
}

/*
 * subtractPeak()
 *
 * Subtract the peak out of the current fit, basically 
 * this just undoes addPeak().
 *
 * fit_data - pointer to a fitData structure.
 * peak - pointer to a peakData structure.
 */
void subtractPeak(fitData *fit_data, peakData *peak)
{
  int j,k,l,m,wx,wy;
  double bg,mag,tmp;
  daoPeak *dao_peak;

  dao_peak = (daoPeak *)peak->peakModel;

  wx = peak->wx;
  wy = peak->wy;

  /* gaussian function */
  l = peak->offset;
  bg = peak->params[BACKGROUND];
  mag = peak->params[HEIGHT];
  for(j=-wy;j<=wy;j++){
    tmp = dao_peak->eyt[j+wy];
    for(k=-wx;k<=wx;k++){
      m = j * fit_data->image_size_x + k + l;
      fit_data->f_data[m] -= mag * tmp * dao_peak->ext[k+wx];
      fit_data->bg_counts[m] -= 1;
      fit_data->bg_data[m] -= (bg + fit_data->scmos_term[m]);
    }
  }
}


/*
 * update2DFixed()
 *
 * Update current fits given fixed x & y width.
 *
 * This procedure is also responsible for flagging peaks
 * that might be bad & that should be removed from fitting.
 *
 * fit_data - pointer to a fitData structure.
 * peak - pointer to a peakData structure.
 */
void update2DFixed(fitData *fit_data, peakData *peak)
{
  // Lapack
  int n = 4, nrhs = 1, lda = 4, ldb = 4, info;

  // Local
  int i,j,k,l,m,wx,wy;
  double fi,xi,xt,ext,yt,eyt,e_t,t1,t2,a1,width;
  double delta[NPEAKPAR];
  double jt[4];
  double jacobian[4];
  double hessian[16];
  daoPeak *dao_peak;

  for(i=0;i<NPEAKPAR;i++){
    delta[i] = 0.0;
  }

  dao_peak = (daoPeak *)peak->peakModel;
  if(peak->status==RUNNING){
    for(j=0;j<4;j++){
      jacobian[j] = 0.0;
    }
    for(j=0;j<16;j++){
      hessian[j] = 0.0;
    }
    l = peak->offset;
    wx = peak->wx;
    wy = peak->wy;
    a1 = peak->params[HEIGHT];
    width = peak->params[XWIDTH];
    for(j=-wy;j<=wy;j++){
      yt = dao_peak->yt[j+wy];
      eyt = dao_peak->eyt[j+wy];
      for(k=-wx;k<=wx;k++){
	m = j * fit_data->image_size_x + k + l;
	fi = fit_data->f_data[m] + fit_data->bg_data[m] / ((double)fit_data->bg_counts[m]);
	xi = fit_data->x_data[m];
	xt = dao_peak->xt[k+wx];
	ext = dao_peak->ext[k+wx];
	e_t = ext*eyt;

	jt[0] = e_t;
	jt[1] = 2.0*a1*width*xt*e_t;
	jt[2] = 2.0*a1*width*yt*e_t;
	jt[3] = 1.0;
	
	// calculate jacobian
	t1 = 2.0*(1.0 - xi/fi);
	jacobian[0] += t1*jt[0];
	jacobian[1] += t1*jt[1];
	jacobian[2] += t1*jt[2];
	jacobian[3] += t1*jt[3];
	  
	// calculate hessian
	t2 = 2.0*xi/(fi*fi);

	// calculate hessian without second derivative terms.
	hessian[0] += t2*jt[0]*jt[0];
	hessian[1] += t2*jt[0]*jt[1];
	hessian[2] += t2*jt[0]*jt[2];
	hessian[3] += t2*jt[0]*jt[3];
	    
	// hessian[4]
	hessian[5] += t2*jt[1]*jt[1];
	hessian[6] += t2*jt[1]*jt[2];
	hessian[7] += t2*jt[1]*jt[3];
	
	// hessian[8]
	// hessian[9]
	hessian[10] += t2*jt[2]*jt[2];
	hessian[11] += t2*jt[2]*jt[3];
	
	// hessian[12]
	// hessian[13]
	// hessian[14]
	hessian[15] += t2*jt[3]*jt[3];
      }
    }

    // subtract the old peak out of the foreground and background arrays.
    subtractPeak(fit_data, peak);
      
    // Use Lapack to solve AX=B to calculate update vector
    dposv_( "Lower", &n, &nrhs, hessian, &lda, jacobian, &ldb, &info );

    if(info!=0){
      peak->status = ERROR;
      fit_data->n_dposv++;
      if(TESTING){
	printf("fitting error! %d %d %d\n", i, info, ERROR);
      }
    }
    else{
      // update params
      delta[HEIGHT]     = jacobian[0];
      delta[XCENTER]    = jacobian[1];
      delta[YCENTER]    = jacobian[2];
      delta[BACKGROUND] = jacobian[3];
      
      if(VERBOSE){
	printf("%d\n", i);
      }
      fitDataUpdate(fit_data, peak, delta);

      // add the new peak to the foreground and background arrays.
      if (peak->status != ERROR){
	addPeak(fit_data, peak);
      }
    }
  }
  if(VERBOSE){
    printf("\n");
  }
}


/*
 * update2D()
 *
 * Update current fits given equal width in x and y.
 *
 * This procedure is also responsible for flagging peaks
 * that might be bad & that should be removed from fitting.
 *
 * fit_data - pointer to a fitData structure.
 * peak - pointer to a peakData structure.
 */
void update2D(fitData *fit_data, peakData *peak)
{
  // Lapack
  int n = 5, nrhs = 1, lda = 5, ldb = 5, info;

  // Local
  int i,j,k,l,m,wx,wy;
  double fi,xi,xt,ext,yt,eyt,e_t,t1,t2,a1,width;
  double delta[NPEAKPAR];
  double jt[5];
  double jacobian[5];
  double hessian[25];
  daoPeak *dao_peak;

  for(i=0;i<NPEAKPAR;i++){
    delta[i] = 0.0;
  }

  dao_peak = (daoPeak *)peak->peakModel;
  if(peak->status==RUNNING){
    for(j=0;j<5;j++){
      jacobian[j] = 0.0;
    }
    for(j=0;j<25;j++){
      hessian[j] = 0.0;
    }
    l = peak->offset;
    wx = peak->wx;
    wy = peak->wy;
    a1 = peak->params[HEIGHT];
    width = peak->params[XWIDTH];
    for(j=-wy;j<=wy;j++){
      yt = dao_peak->yt[j+wy];
      eyt = dao_peak->eyt[j+wy];
      for(k=-wx;k<=wx;k++){
	m = j * fit_data->image_size_x + k + l;
	fi = fit_data->f_data[m] + fit_data->bg_data[m] / ((double)fit_data->bg_counts[m]);
	xi = fit_data->x_data[m];
	xt = dao_peak->xt[k+wx];
	ext = dao_peak->ext[k+wx];
	e_t = ext*eyt;

	jt[0] = e_t;
	jt[1] = 2.0*a1*width*xt*e_t;
	jt[2] = 2.0*a1*width*yt*e_t;
	jt[3] = -a1*xt*xt*e_t-a1*yt*yt*e_t;
	jt[4] = 1.0;
	  
	// calculate jacobian
	t1 = 2.0*(1.0 - xi/fi);
	jacobian[0] += t1*jt[0];
	jacobian[1] += t1*jt[1];
	jacobian[2] += t1*jt[2];
	jacobian[3] += t1*jt[3];
	jacobian[4] += t1*jt[4];
	
	// calculate hessian
	t2 = 2.0*xi/(fi*fi);

	// calculate hessian without second derivative terms.
	hessian[0] += t2*jt[0]*jt[0];
	hessian[1] += t2*jt[0]*jt[1];
	hessian[2] += t2*jt[0]*jt[2];
	hessian[3] += t2*jt[0]*jt[3];
	hessian[4] += t2*jt[0]*jt[4];
	  
	// hessian[5]
	hessian[6] += t2*jt[1]*jt[1];
	hessian[7] += t2*jt[1]*jt[2];
	hessian[8] += t2*jt[1]*jt[3];
	hessian[9] += t2*jt[1]*jt[4];
	    
	// hessian[10]
	// hessian[11]
	hessian[12] += t2*jt[2]*jt[2];
	hessian[13] += t2*jt[2]*jt[3];
	hessian[14] += t2*jt[2]*jt[4];
	  
	// hessian[15]
	// hessian[16]
	// hessian[17]
	hessian[18] += t2*jt[3]*jt[3];
	hessian[19] += t2*jt[3]*jt[4];
	
	// hessian[20]
	// hessian[21]
	// hessian[22]
	// hessian[23]
	hessian[24] += t2*jt[4]*jt[4];
      }
    }
    
    // subtract the old peak out of the foreground and background arrays.
    subtractPeak(fit_data, peak);

    // Use Lapack to solve AX=B to calculate update vector
    dposv_( "Lower", &n, &nrhs, hessian, &lda, jacobian, &ldb, &info );
    
    if(info!=0){
      peak->status = ERROR;
      fit_data->n_dposv++;
      if(TESTING){
	printf("fitting error! %d %d %d\n", i, info, ERROR);
	printf("  %f %f %f %f %f\n", delta[HEIGHT], delta[XCENTER], delta[YCENTER], delta[XWIDTH], delta[BACKGROUND]);
      }
    }
    else{
      // update params
      delta[HEIGHT]     = jacobian[0];
      delta[XCENTER]    = jacobian[1];
      delta[YCENTER]    = jacobian[2];
      delta[XWIDTH]     = jacobian[3];
      delta[YWIDTH]     = jacobian[3];
      delta[BACKGROUND] = jacobian[4];
      
      fitDataUpdate(fit_data, peak, delta);

      // add the new peak to the foreground and background arrays.
      // recalculate peak fit area as the peak width may have changed.
      if (peak->status != ERROR){
	peak->wx = calcWidth(peak->params[XWIDTH], peak->wx);
	peak->wy = peak->wx;
	addPeak(fit_data, peak);
      }
    }
  }
}


/*
 * update3D()
 *
 * Update current fits allowing all parameters to change.
 *
 * This procedure is also responsible for flagging peaks
 * that might be bad & that should be removed from fitting.
 *
 * fit_data - pointer to a fitData structure.
 * peak - pointer to a peakData structure.
 */
void update3D(fitData *fit_data, peakData *peak)
{
  // Lapack
  int n = 6, nrhs = 1, lda = 6, ldb = 6, info;

  // Local
  int i,j,k,l,m,wx,wy;
  double fi,xi,xt,ext,yt,eyt,e_t,t1,t2,a1,a3,a5;
  double delta[NPEAKPAR];
  double jt[6];
  double jacobian[6];
  double hessian[36];
  daoPeak *dao_peak;

  for(i=0;i<NPEAKPAR;i++){
    delta[i] = 0.0;
  }

  dao_peak = (daoPeak *)peak->peakModel;
  if(peak->status==RUNNING){
    for(j=0;j<6;j++){
      jacobian[j] = 0.0;
    }
    for(j=0;j<36;j++){
      hessian[j] = 0.0;
    }
    l = peak->offset;
    wx = peak->wx;
    wy = peak->wy;
    a1 = peak->params[HEIGHT];
    a3 = peak->params[XWIDTH];
    a5 = peak->params[YWIDTH];
    for(j=-wy;j<=wy;j++){
      yt = dao_peak->yt[j+wy];
      eyt = dao_peak->eyt[j+wy];
      for(k=-wx;k<=wx;k++){
	m = j * fit_data->image_size_x + k + l;
	fi = fit_data->f_data[m] + fit_data->bg_data[m] / ((double)fit_data->bg_counts[m]);
	xi = fit_data->x_data[m];
	xt = dao_peak->xt[k+wx];
	ext = dao_peak->ext[k+wx];
	e_t = ext*eyt;

	jt[0] = e_t;
	jt[1] = 2.0*a1*a3*xt*e_t;
	jt[2] = -a1*xt*xt*e_t;
	jt[3] = 2.0*a1*a5*yt*e_t;
	jt[4] = -a1*yt*yt*e_t;
	jt[5] = 1.0;
	    	  
	// calculate jacobian
	t1 = 2.0*(1.0 - xi/fi);
	jacobian[0] += t1*jt[0];
	jacobian[1] += t1*jt[1];
	jacobian[2] += t1*jt[2];
	jacobian[3] += t1*jt[3];
	jacobian[4] += t1*jt[4];
	jacobian[5] += t1*jt[5];

	// calculate hessian
	t2 = 2.0*xi/(fi*fi);

	// hessian without second derivative terms.
	hessian[0] += t2*jt[0]*jt[0];
	hessian[1] += t2*jt[0]*jt[1];
	hessian[2] += t2*jt[0]*jt[2];
	hessian[3] += t2*jt[0]*jt[3];
	hessian[4] += t2*jt[0]*jt[4];
	hessian[5] += t2*jt[0]*jt[5];
	    
	// hessian[6]
	hessian[7]  += t2*jt[1]*jt[1];
	hessian[8]  += t2*jt[1]*jt[2];
	hessian[9]  += t2*jt[1]*jt[3];
	hessian[10] += t2*jt[1]*jt[4];
	hessian[11] += t2*jt[1]*jt[5];
	    
	// hessian[12]
	// hessian[13]
	hessian[14] += t2*jt[2]*jt[2];
	hessian[15] += t2*jt[2]*jt[3];
	hessian[16] += t2*jt[2]*jt[4];
	hessian[17] += t2*jt[2]*jt[5];
	
	// hessian[18]
	// hessian[19]
	// hessian[20]
	hessian[21] += t2*jt[3]*jt[3];
	hessian[22] += t2*jt[3]*jt[4];
	hessian[23] += t2*jt[3]*jt[5];
	    
	// hessian[24]
	// hessian[25]
	// hessian[26]
	// hessian[27]
	hessian[28] += t2*jt[4]*jt[4];
	hessian[29] += t2*jt[4]*jt[5];

	// hessian[30]
	// hessian[31]
	// hessian[32]
	// hessian[33]
	// hessian[34]
	hessian[35] += t2*jt[5]*jt[5];
      }
    }
      
    // subtract the old peak out of the foreground and background arrays.
    subtractPeak(fit_data, peak);

    // Use Lapack to solve AX=B to calculate update vector
    dposv_( "Lower", &n, &nrhs, hessian, &lda, jacobian, &ldb, &info );

    if(info!=0){
      peak->status = ERROR;
      fit_data->n_dposv++;
      if(TESTING){
	printf("fitting error! %d %d %d\n", i, info, ERROR);
      }
    }

    else{
      // update params
      delta[HEIGHT]     = jacobian[0];
      delta[XCENTER]    = jacobian[1];
      delta[XWIDTH]     = jacobian[2];
      delta[YCENTER]    = jacobian[3];
      delta[YWIDTH]     = jacobian[4];
      delta[BACKGROUND] = jacobian[5];

      fitDataUpdate(fit_data, peak, delta);

      // add the new peak to the foreground and background arrays.
      if (peak->status != ERROR){
	peak->wx = calcWidth(peak->params[XWIDTH], peak->wx);
	peak->wy = calcWidth(peak->params[YWIDTH], peak->wy);
	addPeak(fit_data, peak);
      }
    }
  }
}


/*
 * updateZ()
 *
 * Update current fits given x, y width determined by z parameter.
 *
 * This procedure is also responsible for flagging peaks
 * that might be bad & that should be removed from fitting.
 *
 * fit_data - pointer to a fitData structure.
 * peak - pointer to a peakData structure.
 */
void updateZ(fitData *fit_data, peakData *peak)
{
  // Lapack
  int n = 5, nrhs = 1, lda = 5, ldb = 5, info;

  // Local
  int i,j,k,l,m,wx,wy;
  double fi,xi,xt,ext,yt,eyt,e_t,t1,t2,a1,a3,a5;
  double z0,z1,z2,zt,gx,gy;
  double delta[NPEAKPAR];
  double jt[5];
  double jacobian[5];
  double hessian[25];
  daoFit *dao_fit;
  daoPeak *dao_peak;

  for(i=0;i<NPEAKPAR;i++){
    delta[i] = 0.0;
  }

  dao_fit = (daoFit *)fit_data->fitModel;
  dao_peak = (daoPeak *)peak->peakModel;
  if(peak->status==RUNNING){
    for(j=0;j<5;j++){
	jacobian[j] = 0.0;
    }
    for(j=0;j<25;j++){
      hessian[j] = 0.0;
    }
    l = peak->offset;
    wx = peak->wx;
    wy = peak->wy;
    a1 = peak->params[HEIGHT];
    a3 = peak->params[XWIDTH];
    a5 = peak->params[YWIDTH];
    
    // dwx/dz calcs
    z0 = (peak->params[ZCENTER] - dao_fit->wx_z_params[1]) / dao_fit->wx_z_params[2];
    z1 = z0*z0;
    z2 = z1*z0;
    zt = 2.0*z0 + 3.0*dao_fit->wx_z_params[3]*z1 + 4.0*dao_fit->wx_z_params[4]*z2;
    gx = -2.0*zt/(dao_fit->wx_z_params[0]*dao_peak->wx_term);

    // dwy/dz calcs
    z0 = (peak->params[ZCENTER] - dao_fit->wy_z_params[1]) / dao_fit->wy_z_params[2];
    z1 = z0*z0;
    z2 = z1*z0;
    zt = 2.0*z0 + 3.0*dao_fit->wy_z_params[3]*z1 + 4.0*dao_fit->wy_z_params[4]*z2;
    gy = -2.0*zt/(dao_fit->wy_z_params[0]*dao_peak->wy_term);
    for(j=-wy;j<=wy;j++){
      yt = dao_peak->yt[j+wy];
      eyt = dao_peak->eyt[j+wy];
      for(k=-wx;k<=wx;k++){
	m = j*fit_data->image_size_x + k + l;
	fi = fit_data->f_data[m] + fit_data->bg_data[m] / ((double)fit_data->bg_counts[m]);
	xi = fit_data->x_data[m];
	xt = dao_peak->xt[k+wx];
	ext = dao_peak->ext[k+wx];
	e_t = ext*eyt;
	
	// first derivatives
	jt[0] = e_t;
	jt[1] = 2.0*a1*a3*xt*e_t;
	jt[2] = 2.0*a1*a5*yt*e_t;
	jt[3] = -a1*xt*xt*gx*e_t-a1*yt*yt*gy*e_t;
	jt[4] = 1.0;
	  
	// calculate jacobian
	t1 = 2.0*(1.0 - xi/fi);
	jacobian[0] += t1*jt[0];
	jacobian[1] += t1*jt[1];
	jacobian[2] += t1*jt[2];
	jacobian[3] += t1*jt[3];
	jacobian[4] += t1*jt[4];
	
	// calculate hessian
	t2 = 2.0*xi/(fi*fi);
	
	// calculate hessian without second derivative terms.
	hessian[0] += t2*jt[0]*jt[0];
	hessian[1] += t2*jt[0]*jt[1];
	hessian[2] += t2*jt[0]*jt[2];
	hessian[3] += t2*jt[0]*jt[3];
	hessian[4] += t2*jt[0]*jt[4];
	
	// hessian[5]
	hessian[6] += t2*jt[1]*jt[1];
	hessian[7] += t2*jt[1]*jt[2];
	hessian[8] += t2*jt[1]*jt[3];
	hessian[9] += t2*jt[1]*jt[4];
	    
	// hessian[10]
	// hessian[11]
	hessian[12] += t2*jt[2]*jt[2];
	hessian[13] += t2*jt[2]*jt[3];
	hessian[14] += t2*jt[2]*jt[4];
	  
	// hessian[15]
	// hessian[16]
	// hessian[17]
	hessian[18] += t2*jt[3]*jt[3];
	hessian[19] += t2*jt[3]*jt[4];

	// hessian[20]
	// hessian[21]
	// hessian[22]
	// hessian[23]
	hessian[24] += t2*jt[4]*jt[4];
      }
    }

    // subtract the old peak out of the foreground and background arrays.
    subtractPeak(fit_data, peak);
      
    // Use Lapack to solve AX=B to calculate update vector
    dposv_( "Lower", &n, &nrhs, hessian, &lda, jacobian, &ldb, &info );

    if(info!=0){
      peak->status = ERROR;
      fit_data->n_dposv++;
      if(TESTING){
	printf("fitting error! %d %d %d\n", i, info, ERROR);
      }
    }
    else{
      // update params
      delta[HEIGHT]     = jacobian[0];
      delta[XCENTER]    = jacobian[1];
      delta[YCENTER]    = jacobian[2];
      delta[ZCENTER]    = jacobian[3];
      delta[BACKGROUND] = jacobian[4];
      
      fitDataUpdate(fit_data, peak, delta);

      // add the new peak to the foreground and background arrays.
      if (peak->status != ERROR){
	// calculate new x,y width, update fit area.
	calcWidthsFromZ(fit_data, peak);
	peak->wx = calcWidth(peak->params[XWIDTH], peak->wx);
	peak->wy = calcWidth(peak->params[YWIDTH], peak->wy);
	addPeak(fit_data, peak);
      }
    }
  }
  if(VERBOSE){
    printf("\n");
  }
}

/*
 * The MIT License
 *
 * Copyright (c) 2013 Zhuang Lab, Harvard University
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */
