/* Fanatics Sunday TD terms and what is verified about them (researched 2026-10-10). Served to the browser (config/ is not deployed), so it lives in shared/.
 * Status values: 'verified-secondary' (stated by the Fanatics marketing blog or a third-party page; NOT the official rules), 'user-supplied', 'conflicting', 'unverified'.
 * Nothing is marked officially verified because the official terms could not be retrieved. */
(function(root){
'use strict';
const TERMS={
 "schema": "going-fanatics-td-terms-1",
 "promotion": "Fanatics Sportsbook NFL Jackpots / Triple Touchdown Jackpot (Sunday)",
 "researched_at": "2026-10-10",
 "read_me": "Official Fanatics rules could not be retrieved: sportsbook.fanatics.com/promotions returned 404 and no official terms page was found. The two public pages that describe the promotion are a Fanatics marketing blog (not the rules) and a third-party promotions page. Nothing here is a confirmed official term. `user-supplied` values come from the user; `verified-secondary` values are stated by the Fanatics blog or the third-party page; `conflicting` means sources differ; `unverified` means no source states it.",
 "sources": [
  {
   "id": "fanatics-blog",
   "url": "https://betfanatics.com/blog/nfl-jackpots-what-is-nfl-jackpots-and-how-can-you-win-a-share-of-250k-fancash-this-weekend",
   "kind": "Fanatics marketing blog (not the rules)"
  },
  {
   "id": "third-party",
   "url": "https://sportsbooksonline.com/promotions/fanatics-triple-touchdown-jackpot",
   "kind": "third-party promotions summary; cites no official rules link"
  }
 ],
 "terms": {
  "state": {
   "value": "OH",
   "status": "user-supplied",
   "note": "Fanatics is live in Ohio, but no source states that this promotion is available in Ohio (the third-party page says only 'an eligible state')."
  },
  "legs": {
   "value": 3,
   "status": "conflicting",
   "source": "fanatics-blog says 'at least three legs'; third-party says three-leg parlay",
   "note": "The engine builds exactly three legs, as the user specified. A slip with more legs may also qualify."
  },
  "market": {
   "value": "anytime touchdown scorer",
   "status": "verified-secondary",
   "source": "fanatics-blog, third-party"
  },
  "minStake": {
   "value": 5,
   "status": "verified-secondary",
   "source": "fanatics-blog, third-party ($5 minimum; third-party says cash stake)"
  },
  "minCombinedAmerican": {
   "value": 2000,
   "status": "conflicting",
   "source": "fanatics-blog says 'three legs at odds of +2000 or longer' without saying combined or per leg; third-party says the three-leg parlay must be +2000 or longer",
   "note": "Treated as the combined parlay price, as the user supplied. Per-leg interpretation is not supported by the engine."
  },
  "differentGames": {
   "value": true,
   "status": "conflicting",
   "source": "third-party intro says three different games; its rules line says three different players from Sunday games; the Fanatics blog does not say",
   "note": "The default view uses three different games, which satisfies both readings."
  },
  "entryLimit": {
   "value": null,
   "status": "conflicting",
   "source": "third-party says max 5 entries per Sunday; the Fanatics blog does not state a limit",
   "note": "Entry limit not verified. The feature shows five alternatives but does not claim you may enter all five."
  },
  "prizeSharing": {
   "value": "shared pool paid in FanCash",
   "status": "verified-secondary",
   "source": "fanatics-blog: pool split among qualifying winners; third-party: split equally among winning entries; amount stated as up to $250,000 (third-party also says $200,000 base)",
   "note": "No estimated dollar value is assigned to the prize anywhere in GOING."
  },
  "lock": {
   "value": "before 1:00 PM ET Sunday",
   "status": "verified-secondary",
   "source": "fanatics-blog says entries must be submitted before the 1 p.m. ET kickoff deadline; third-party gives no cutoff",
   "note": "Place the slip before 1:00 PM ET. Whether a leg from a later game is allowed was not verified."
  },
  "voidLeg": {
   "value": "entry disqualified",
   "status": "unverified",
   "source": "third-party only: any voided leg or Fair Play leg disqualifies the entry",
   "note": "Not confirmed by the Fanatics blog."
  },
  "window": {
   "value": "Sundays 2026-09-13 to 2026-10-25",
   "status": "conflicting",
   "source": "third-party gives that window; the Fanatics blog says each week through the NFL season",
   "note": "Check that the promotion is still running on the chosen Sunday."
  },
  "alternativeCombinations": {
   "value": null,
   "status": "unverified",
   "note": "No source says whether several different slips from the same customer are allowed beyond the third-party entry limit."
  },
  "eligibilityToQualify": {
   "value": null,
   "status": "unverified",
   "note": "GOING cannot tell whether your account qualifies (age, location, verification, 'directly offered')."
  }
 }
};
root.GoingFanaticsTDTerms=TERMS;
if(typeof module!=='undefined')module.exports=TERMS;
})(typeof globalThis==='undefined'?this:globalThis);
