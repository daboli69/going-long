// Local-only presentation export. Uses the Codex-provided Artifact Tool runtime.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';

const [input, workspace] = process.argv.slice(2);
if (!input || !workspace) throw new Error('Provide projection JSON and a workspace containing the bundled node_modules junction');
const require = createRequire(path.join(path.resolve(workspace), 'artifact_entry.cjs'));
const {Workbook, SpreadsheetFile} = await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const data = JSON.parse(await fs.readFile(input, 'utf8'));
const workbook = Workbook.create();
const base = input.replace(/\.json$/i, '');
const definitions = [
  {name: 'Games', type: 'game', columns: [
    ['Game','game_id',27], ['Market','stat',12], ['Independent','projection',15], ['Spread','spread_display',16],
    ['10%','q10',12], ['50%','q50',12], ['90%','q90',12], ['Simulation independent','sim_independent_projection',19],
    ['Simulation market anchor','simulator_v1_projection',20], ['Market line','market_line',14], ['P cover / over','p_over',15],
    ['Projection gap','gap',16], ['Line status','line_status',18]]},
  {name: 'Players', type: 'player', columns: [
    ['Game','game_id',27], ['Team','team',10], ['Player','name',25], ['Stat','stat',15], ['Independent','projection',15],
    ['Member min','member_min',14], ['Member max','member_max',14], ['10%','q10',12], ['50%','q50',12], ['90%','q90',12],
    ['Market line','market_line',14], ['P over','p_over',13], ['P push','p_push',13], ['Gap','gap',13], ['Book','book',18],
    ['Line status','line_status',18], ['Market probability','market_probability',18], ['Market-informed','market_informed_projection',18],
    ['Members','members',62], ['Interval method','interval_source',74]]},
  {name: 'First TD', type: 'first_td', columns: [
    ['Game','game_id',27], ['Team','team',10], ['Player','name',32], ['Ensemble-informed','projection',19],
    ['Structural','structural_probability',15], ['Book','book',18], ['Market probability','market_probability',19], ['Gap','gap',13],
    ['Line status','line_status',18]]}
];
const previews = [];
for (const definition of definitions) {
  let rows = data.rows.filter(row => row.row_type === definition.type);
  if (definition.type === 'first_td') {
    // One categorical probability per player/game, even with several price books.
    const unique = new Map();
    for (const row of rows) {
      const key = `${row.game_id}|${row.pid}`;
      const old = unique.get(key);
      if (!old || (row.line_age_hours ?? Infinity) < (old.line_age_hours ?? Infinity)) unique.set(key, row);
    }
    rows = [...unique.values()];
  }
  const sheet = workbook.worksheets.add(definition.name);
  sheet.showGridLines = false;
  sheet.tabColor = '#193B58';
  sheet.getRange('A2').values = [[`NFL projections 2026 week ${data.week}`]];
  sheet.getRange('A2').format.font = {name:'Arial',size:14,bold:true,color:'#193B58'};
  sheet.getRange('A3').values = [[`Unpromoted shadow forecasts. Training cutoff: ${data.training_cutoff_date}.`]];
  sheet.getRange('A4').values = [[definition.type === 'first_td'
    ? 'First offensive rushing/receiving TD. Passing, defensive and special-teams TDs excluded.'
    : 'Source: archived lab forecasts and timestamped local GOING quotes. Market lines are benchmarks.']];
  sheet.getRange('A3:A4').format.font = {name:'Arial',size:10,color:'#526271'};
  const headers = definition.columns.map(c=>c[0]);
  const matrix = [headers, ...rows.map(row => definition.columns.map(([,key]) => {
    const value = row[key];
    return value === undefined || value === null || (typeof value === 'number' && !Number.isFinite(value)) ? null
      : typeof value === 'object' ? JSON.stringify(value) : value;
  }))];
  sheet.getRangeByIndexes(5,0,matrix.length,headers.length).values = matrix;
  const full = sheet.getRangeByIndexes(5,0,matrix.length,headers.length);
  full.format.font = {name:'Arial',size:10,color:'#172936'};
  full.format.verticalAlignment = 'center';
  full.format.rowHeight = 22;
  const head = sheet.getRangeByIndexes(5,0,1,headers.length);
  head.format = {fill:'#193B58',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,
                 horizontalAlignment:'center',verticalAlignment:'center',rowHeight:38};
  definition.columns.forEach(([,key,width],j) => {
    const column = sheet.getRangeByIndexes(5,j,matrix.length,1);
    column.format.columnWidth = width;
    if (rows.length && ['projection','member_min','member_max','q10','q50','q90','market_line','gap',
                       'sim_independent_projection','simulator_v1_projection','market_informed_projection'].includes(key)) {
      sheet.getRangeByIndexes(6,j,rows.length,1).setNumberFormat('0.0');
    }
    if (rows.length && (key.startsWith('p_') || key === 'market_probability' || key === 'structural_probability' ||
        (definition.type === 'first_td' && ['projection','gap'].includes(key)))) {
      sheet.getRangeByIndexes(6,j,rows.length,1).setNumberFormat('0.0%');
    }
    if (rows.length && key === 'line_status') {
      sheet.getRangeByIndexes(6,j,rows.length,1).conditionalFormats.add('containsText', {
        text:'stale',format:{fill:'#FFF0C2',font:{color:'#765400',bold:true}}});
    }
  });
  if (rows.length) {
    const table = sheet.tables.add(`A6:${String.fromCharCode(64+headers.length)}${rows.length+6}`, true,
                                   `Projections${definition.name.replaceAll(' ','')}`);
    table.showFilterButton = true;
    // Small, transparent live gap calculations over the forecast/quote inputs.
    if (definition.type === 'game') {
      sheet.getRangeByIndexes(6,11,rows.length,1).formulas = rows.map((_,i)=>[
        `=IF(AND(ISNUMBER(C${i+7}),ISNUMBER(J${i+7})),C${i+7}-J${i+7},"n.a.")`]);
    } else if (definition.type === 'first_td') {
      sheet.getRangeByIndexes(6,7,rows.length,1).formulas = rows.map((_,i)=>[
        `=IF(ISNUMBER(G${i+7}),D${i+7}-G${i+7},"n.a.")`]);
    }
  }
  sheet.freezePanes.freezeRows(6);
  sheet.freezePanes.freezeColumns(definition.type === 'game' ? 1 : 3);
  previews.push({name:definition.name,range:`A1:${definition.type === 'player' ? 'N' : definition.type === 'game' ? 'M' : 'I'}${Math.min(rows.length+6,18)}`});
}
workbook.recalculate();
const errors = await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!',
  options:{useRegex:true,maxResults:20},summary:'Projection export formula error scan',maxChars:2000});
console.log(errors.ndjson);
for (const preview of previews) {
  const inspected = await workbook.inspect({kind:'table',range:`'${preview.name}'!${preview.range}`,
    include:'values,formulas',tableMaxRows:8,tableMaxCols:5,maxChars:1800});
  console.log(inspected.ndjson);
  const blob = await workbook.render({sheetName:preview.name,range:preview.range,scale:1.5,format:'png'});
  const imagePath = path.join(workspace, `week${data.week}_${preview.name.replaceAll(' ','_')}.png`);
  await fs.writeFile(imagePath,new Uint8Array(await blob.arrayBuffer()));
}
const file = await SpreadsheetFile.exportXlsx(workbook);
await file.save(`${base}.xlsx`);
console.log(JSON.stringify({xlsx:`${base}.xlsx`,sheets:definitions.map(d=>d.name)}));
