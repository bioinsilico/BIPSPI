import sys, os
from sklearn.metrics import roc_auc_score, recall_score, precision_score, roc_curve
import pandas as pd
import numpy as np
from evaluation.evaluateScoresList import evaluateScoresLists

DO_ROC_CURVE= False

#DO_SEQ_AVERAGING=True
DO_SEQ_AVERAGING=False

#BINDING_CMAPS_PATH="/home/rsanchez/Tesis/rriPredMethod/data/ppdockingBenchData/newCodeData/computedFeatures/common/contactMapsBinding"
BINDING_CMAPS_PATH=None # if None, contact maps contained in the results file will be used, otherwise, new contacts will be added from the files in the path

def averageScores(scoresDf):
  labels_list=[]
  scores_list=[]
  for chain in scoresDf["chainId"].unique():
    df= scoresDf.loc[scoresDf["chainId"]==chain,:]
    result= [ ((int(elem), ""), (score, label)) if elem[-1].isdigit() else ((int(elem[:-1]), elem[-1]), (score, label)) 
                                for elem,score,label in zip(df["resId"], df["prediction"], df["categ"]) ]
    result.sort(key= lambda x: x[0])
    result= zip(* result)[1]
    scores, labels= zip(* result)
    scores= list(np.convolve(scores, np.array([1, 3, 1])/5.0, mode='same')+ np.array(scores))
    labels_list+= labels
    scores_list+= scores
  return scores_list, labels_list
  
def loadResults( resultsPath, fnameResults, cMapsPath=BINDING_CMAPS_PATH):
  prefix= fnameResults.split("_")[0].split(".")[0]
  if fnameResults.endswith(".lig"):
    chainType="l"
  else:
    chainType="r"
    
  scoresDf= pd.read_table(os.path.join(resultsPath, fnameResults), comment="#", sep="\s+", dtype={"resId":str, "chainId":str})
  if not cMapsPath is None:
    newCmapSet=set([])
    for fname in os.listdir(cMapsPath):
      #print(fnameResults, fname, prefix, os.path.join(cMapsPath,fname))
      if ((chainType=="l" and "_l_" in fname) or (chainType=="r" and "_r_" in fname)) and fname.startswith(prefix):
        df= pd.read_table(os.path.join(cMapsPath,fname),sep='\s+', header='infer', comment="#", 
                          dtype= {"chainIdL":str, "chainIdR":str, "structResIdL":str, "structResIdR":str,
                                        "chainId":str, "structResId":str,  "resId":str})
        for i in range(df.shape[0]):
          chainId, resId, categ= df.iloc[i,:]
          if categ==1:
            newCmapSet.add((chainId, resId))
    for chainId, resId in newCmapSet:
      scoresDf.loc[(scoresDf["chainId"]==chainId) & (scoresDf["resId"]==resId),"categ"]=1
      
  return scoresDf
  
def get_single_chain_statistics(prefix, labels, scores):
  EVAL_PAIRS_AT= [ 2**3, 2**4]
  precisionAt=[]
  recallAt=[]
  scores= np.array(scores)
  labels= np.array(labels)
  try:
    roc_complex= roc_auc_score(labels, scores)
  except ValueError:
    roc_complex= np.nan
  probability_sorted_indexes = scores.argsort(axis=0)
  probability_sorted_indexes = probability_sorted_indexes[::-1]
  for evalPoint in EVAL_PAIRS_AT:
    try:
      label_predictions= np.ones(scores.shape[0])* np.min( labels)
      label_predictions[probability_sorted_indexes[0 : evalPoint]]= np.repeat(1, evalPoint)
      precisionAt.append( precision_score(labels[probability_sorted_indexes[0 : evalPoint]],
                                        label_predictions[probability_sorted_indexes[0 : evalPoint]]))
      recallAt.append( recall_score(labels, label_predictions))
#      print(sum(labels==1), sum(label_predictions==1),precisionAt[-1], recallAt[-1])
    except IndexError:
      precisionAt.append( 0.0)
      recallAt.append( 0.0)
  summary= pd.DataFrame({"pdb":[prefix]})
  summary["auc_chains"]= [roc_complex] 
  for evalPoint, precisionAt, recallAt in zip(EVAL_PAIRS_AT,precisionAt, recallAt):
    summary["prec_%d"%evalPoint]= [precisionAt]
    summary["reca_%d"%evalPoint]= [recallAt]
    
  rocCurve= None
  if DO_ROC_CURVE:
    fpr, tpr, __= roc_curve(labels, scores)
    rocCurve= (fpr, tpr, roc_complex)
  return summary, rocCurve
  
def getOptimThr(resultsPath, useSeqAvera= DO_SEQ_AVERAGING):
  allScores=[]
  allLabels=[]
  perComplexSummaries=[]
  rocCurves= []
  for fname in sorted(os.listdir(resultsPath)):
    print(fname)
    if fname.endswith(".rec") or fname.endswith(".lig"):
      results= loadResults( resultsPath, fname)
      if results is None: print("skip"); continue
      if useSeqAvera:
        scores, labels= averageScores(results)
      else:
        scores= list(results["prediction"].values)
        labels= list(results["categ"].values)

      summary, rocCurve= get_single_chain_statistics(fname, labels, scores)
      if rocCurve: rocCurves.append(rocCurve)
      perComplexSummaries.append(summary)
#      print("%s %f"%(fname,roc_complex))
      allScores+= scores
      allLabels+= labels

  summary= pd.concat(perComplexSummaries, ignore_index=True)
  means= summary.mean(axis=0)
  summary= summary.append( summary.ix[summary.shape[0]-1,:],ignore_index=True )
  summary.ix[summary.shape[0]-1,0]=  "mean"
  summary.ix[summary.shape[0]-1, 1:]=  means

  evaluateScoresLists(allLabels, allScores, summary, summary.iloc[-1,1], None if not DO_ROC_CURVE else rocCurves)

if __name__=="__main__":
  '''
python -m evaluation.getBestThr_bindingSite  ~/Tesis/rriPredMethod/data/bench5Data/newCodeData/results/mixed_2/
  '''
  resultsPath= os.path.expanduser("~/Tesis/rriPredMethod/data/bench5Data/newCodeData/results/mixed_2/")
  if len(sys.argv)==2:
    resultsPath= sys.argv[1]
  getOptimThr(resultsPath)
  
