(function(root){
'use strict';
const MARKET={spreads:'spread',spread:'spread',totals:'total',total:'total',h2h:'moneyline',moneyline:'moneyline',player_passing_yards:'pass_yds',player_rushing_yards:'rush_yds',player_receiving_yards:'rec_yds',player_receptions:'receptions',player_passing_tds:'pass_tds',player_rushing_tds:'rush_tds',player_receiving_tds:'rec_tds'};
const clean=value=>String(value??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'');
const number=value=>Number.isFinite(Number(value))?String(Number(value)):'none';
function kickoff(value){const time=Date.parse(value);return Number.isFinite(time)?new Date(time).toISOString():'unknown';}
function marketParts(value,explicit){
 let market=clean(value),period=clean(explicit||'');
 if(/_1h$/.test(market)){market=market.slice(0,-3);period=period||'first_half';}
 if(/_1q$/.test(market)){market=market.slice(0,-3);period=period||'first_quarter';}
 return {market:MARKET[market]||market,period:period||'full_game'};
}
function eventId(row){return ['event-v1',clean(row.sport),clean(row.away),clean(row.home),kickoff(row.kickoff)].join('|');}
function identity(row){
 const part=marketParts(row.market,row.period),kind=clean(row.kind||((row.profileId||row.player)?'prop':'game'));
 const entity=kind==='prop'?clean(row.profileId||row.player):clean(row.team||'game');
 const rules=clean(row.rules||(kind==='prop'?'player_must_participate':'including_overtime'));
 return ['contract-v1',eventId(row),kind,entity,part.market,part.period,clean(row.side),number(row.line),rules].join('|');
}
function describe(row){const part=marketParts(row.market,row.period);return {schema_version:1,id:identity(row),event_id:eventId(row),kind:clean(row.kind),entity:clean(row.profileId||row.player||row.team||'game'),market:part.market,period:part.period,side:clean(row.side),line:Number.isFinite(Number(row.line))?Number(row.line):null,rules:clean(row.rules||((row.kind==='prop')?'player_must_participate':'including_overtime'))};}
root.GoingFootballOpportunity={eventId,identity,describe,marketParts};
if(typeof module!=='undefined')module.exports=root.GoingFootballOpportunity;
})(globalThis);
