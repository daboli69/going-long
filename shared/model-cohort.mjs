export function modelCohort(p){
 if(p.model_cohort)return p.model_cohort;
 const e=p.model_evidence||p,season=e.seasonEvidence,game=e.gameSeasonEvidence;
 if(String(season?.method||game?.policy||'').includes('80% current'))return 'current-80-20';
 if(e.roleEvidence||season)return 'role-aware-equal-weight';
 return 'legacy';
}
export const COHORT_LABELS={'current-80-20':'Current 80/20 policy','role-aware-equal-weight':'Role-aware, before 80/20','legacy':'Legacy model','going-picks-v1':'GOING Picks · football case v1'};
