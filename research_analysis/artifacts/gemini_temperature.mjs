import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const [source, output, previewDir] = process.argv.slice(2);
if (!source || !output || !previewDir) throw new Error('Usage: node gemini_temperature.mjs metrics.json output.xlsx preview-directory');
const data = JSON.parse(await fs.readFile(source, 'utf8'));
if (data.metrics.length !== 16 || !data.records.length) throw new Error('Expected sixteen metrics and at least one endpoint');
function column(n) { let s=''; for (;n;n=Math.floor((n-1)/26)) s=String.fromCharCode(65+(n-1)%26)+s; return s; }
const lastCol=column(data.records.length+2);
const wb = Workbook.create();
const sheet = wb.worksheets.add('16 metrics');
sheet.showGridLines = false;
sheet.tabColor = '#243B53';
sheet.getRange('A2').values = [['Exploratory ADaM experiment results']];
sheet.getRange('A2').format.font = {name:'Arial',size:14,bold:true};
sheet.getRange('A3').values = [['Single attempts. Historical controls are nonconcurrent. Repair metrics are not applicable to initial-only endpoints.']];
const headers = ['No.','Metric',...data.records.map(r=>r.endpoint_label || `${r.model} / ${r.condition}`)];
const matrix = [headers,...data.metrics.map((metric,i)=>[i+1,metric,...data.records.map(r=>r.values[i])])];
sheet.getRange(`A5:${lastCol}21`).values = matrix;
sheet.getRange(`A5:${lastCol}21`).format.font = {name:'Arial',size:10,color:'#172B4D'};
sheet.getRange(`A5:${lastCol}21`).format.wrapText = true;
sheet.getRange(`A5:${lastCol}21`).format.verticalAlignment = 'top';
sheet.getRange(`A5:${lastCol}5`).format = {fill:'#243B53',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center'};
sheet.getRange(`A5:${lastCol}5`).format.rowHeight = 48;
sheet.getRange('A5:A21').format.columnWidth = 5;
sheet.getRange('B5:B21').format.columnWidth = 38;
sheet.getRange(`C5:${lastCol}21`).format.columnWidth = 56;
for (let i=0;i<16;i++) {
  const lines = Math.max(...matrix[i+1].map((v,j)=>String(v).split('\n').reduce((n,s)=>n+Math.max(1,Math.ceil(s.length/(j===1?43:65))),0)));
  sheet.getRange(`A${i+6}:${lastCol}${i+6}`).format.rowHeight = Math.max(36,lines*14+12);
  if (i%2===1) sheet.getRange(`A${i+6}:${lastCol}${i+6}`).format.fill = '#F0F4F8';
}
sheet.freezePanes.freezeRows(5);
sheet.freezePanes.freezeColumns(2);

const numeric = wb.worksheets.add('Endpoint data');
numeric.showGridLines = false;
const numericHeaders = ['Endpoint','Model','Condition','Temperature','Phase','Controller status','P21 report usable','Dataset-rule pairs','Finding instances','Distinct rules','Cost estimate (USD)','Agent time (seconds)','Tool calls','Failed tool calls'];
const numericRows = [];
for (const r of data.records) {
  for (const phase of r.condition === 'initial_only' ? ['initial'] : ['initial','final']) {
    const n=r.numeric[phase] || {};
    numericRows.push([r.endpoint_label || `${r.model} / ${r.condition}`,r.model,r.condition,r.temperature ?? 'Historical default',phase,r.controller_status || r.status,
      n.report_usable ?? null,n.dataset_rule_pairs ?? null,n.finding_instances ?? null,n.distinct_rules ?? null,n.cost_estimate_usd ?? null,n.agent_seconds ?? null,n.tool_calls ?? null,n.tool_failures ?? null]);
  }
}
numeric.getRangeByIndexes(0,0,numericRows.length+1,numericHeaders.length).values = [numericHeaders,...numericRows];
numeric.getRangeByIndexes(0,0,numericRows.length+1,numericHeaders.length).format.font = {name:'Arial',size:10,color:'#172B4D'};
numeric.getRangeByIndexes(0,0,numericRows.length+1,numericHeaders.length).format.rowHeight = 24;
numeric.getRange('A1:N1').format = {fill:'#243B53',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center'};
numeric.getRange('A1:N1').format.rowHeight = 42;
numeric.getRange('A:A').format.columnWidth=54;
numeric.getRange('B:F').format.columnWidth=22;
numeric.getRange('G:N').format.columnWidth=19;
numeric.getRange(`H2:J${numericRows.length+1}`).setNumberFormat('#,##0');
numeric.getRange(`K2:K${numericRows.length+1}`).setNumberFormat('$0.0000');
numeric.getRange(`L2:L${numericRows.length+1}`).setNumberFormat('0.0');
numeric.getRange(`M2:N${numericRows.length+1}`).setNumberFormat('#,##0');
numeric.freezePanes.freezeRows(1);
numeric.freezePanes.freezeColumns(1);
const notesStart=numericRows.length+4;
numeric.getRange(`A${notesStart}`).values=[['Source: metrics.json. Blank numeric cells mean unavailable. Costs are telemetry estimates, not invoices.']];
data.limitations.forEach((text,i)=>{numeric.getRange(`A${notesStart+2+i}`).values=[[text]];});
wb.recalculate();
const recentStart=column(Math.max(3,data.records.length));
console.log((await wb.inspect({kind:'table',range:`16 metrics!${recentStart}5:${lastCol}9`,include:'values',tableMaxRows:5,tableMaxCols:4,tableMaxCellChars:180,maxChars:2500})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:1200})).ndjson);
await fs.mkdir(previewDir,{recursive:true});
for (const [sheetName,range,name] of [['16 metrics',`${recentStart}5:${lastCol}9`,'recent-results'],['16 metrics','A5:D9','historical'],['Endpoint data','A1:F7','endpoint-data']]) {
  const blob = await wb.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(path.join(previewDir,`${name}.png`),new Uint8Array(await blob.arrayBuffer()));
}
await fs.mkdir(path.dirname(output),{recursive:true});
await (await SpreadsheetFile.exportXlsx(wb)).save(output);
console.log('Saved sixteen-metric workbook with numeric endpoint data.');
