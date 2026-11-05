import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';

const [input,outputDir]=process.argv.slice(2);
if(!input||!outputDir)throw Error('usage: builder comparison.json output_dir');
const data=JSON.parse(await fs.readFile(input,'utf8'));
if(data.records.length!==5||data.table_rows.length!==19)throw Error('Expected five labelled columns and all nineteen metrics');
const wb=Workbook.create();const summary=wb.worksheets.add('Comparison');const detail=wb.worksheets.add('Metric details');
for(const s of [summary,detail])s.showGridLines=false;
const colors={navy:'#243B53',light:'#F0F4F8',ink:'#172B4D',muted:'#526777',amber:'#FFF1CF'};
const literal=x=>typeof x==='string'&&x.startsWith('=')?"'"+x:x;
summary.getRange('A1:G30').format.font={name:'Arial',size:10,color:colors.ink};
summary.getRange('A2').values=[[data.comparison_complete?'Full-benchmark AI-431 model results':'INTERIM — AI-431 execution incomplete']];summary.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:colors.navy};
summary.getRange('A3').values=[[data.comparison_complete?'Five planned endpoints; same new variable pipeline; gateway did not start.':'Claude ended; three qualified models await disk space; gateway HTTP403.']];
summary.getRange('A3').format.font={name:'Arial',size:10,color:colors.muted};
summary.getRange('A4').values=[['Source: https://github.com/lyc0603/clinical_bench/tree/main/pre_experiment/results/ai431-full-models-2026-11-05']];
summary.getRange('A4').format.font={name:'Arial',size:10,italic:true,color:colors.muted};
summary.getRange('A6:G6').values=[data.table_headers.map(literal)];
const rows=data.table_rows.map(r=>r.map(literal));
// Preserve true scalar counts as numeric cells; compound results remain text.
for(let c=0;c<5;c++){
 const r=data.records[c];const v=r.metrics[3].value;
 const count=v?.posthoc_terminal_dataset_rule_pairs??v?.final_primary_dataset_rule_pairs;
 if(typeof count==='number')rows[3][c+2]=count;
}
summary.getRange('A7:G25').values=rows;
summary.getRange('A6:G6').format={fill:colors.navy,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:52};
summary.getRange('A7:G25').format={wrapText:true,verticalAlignment:'center',rowHeight:45};
summary.getRange('A6:A25').format.columnWidth=5;summary.getRange('B6:B25').format.columnWidth=43;
summary.getRange('C6:G25').format.columnWidth=39;
for(let r=7;r<=25;r++)if(r%2===1)summary.getRange(`A${r}:G${r}`).format.fill=colors.light;
summary.getRange('A7:A25').setNumberFormat('0');summary.getRange('C10:G10').setNumberFormat('#,##0');summary.getRange('C10:G10').format.horizontalAlignment='center';
summary.getRange('A16:G16').format.rowHeight=138;
summary.getRange('A14:G14').format.rowHeight=64;
summary.getRange('A20:G20').format.rowHeight=62;
summary.getRange('A25:G25').format.rowHeight=150;
summary.getRange('F7:F25').format.font={name:'Arial',size:10,color:colors.muted};
summary.freezePanes.freezeRows(6);summary.freezePanes.freezeColumns(2);summary.tabColor=colors.navy;
summary.getRange('I6').values=[['Interpretation']];summary.getRange('I6').format.font={name:'Arial',size:10,bold:true,color:colors.navy};
const notes=[
 'Unavailable is different from zero.',
 'P21 findings are not validator execution failures.',
 'No complete initial P21 comparator: metrics 5 and 7 are unavailable.',
 'All qualified models use the same new variable pipeline version.',
 'Strict reconstruction failures are retained, including tiny float differences.',
 'Auxiliary checks cover selected NPI/TTE derivations only.',
 'No architecture or model superiority inference from single attempts.',
 'Gateway identity does not authenticate an OpenAI upstream model.'
];
summary.getRange('I7:I14').values=notes.map(x=>[x]);summary.getRange('I6:H14').format.columnWidth=98;summary.getRange('I7:I14').format.font={name:'Arial',size:10,color:colors.muted};summary.getRange('I7:I14').format.wrapText=false;

const details=[];
function leaves(value,prefix,callback){
 if(value!==null&&typeof value==='object'){
  const entries=Object.entries(value);if(!entries.length)callback(prefix,null);
  for(const [key,v] of entries)leaves(v,prefix?prefix+'.'+key:key,callback);
 }else callback(prefix,value);
}
function unit(number,key,value){
 if(typeof value!=='number')return '';
 if(key.endsWith('rate'))return 'proportion';
 if(key.includes('seconds'))return 'seconds';
 if(number===15)return 'minutes';
 if(key.includes('calls'))return 'calls';
 if(key.includes('tokens'))return 'tokens';
 if(number===17)return 'datasets';if(number===18)return 'variables';
 if([8,9,10,11].includes(number))return 'records';return 'count';
}
for(const record of data.records)for(const metric of record.metrics)leaves(metric.value,'',(component,value)=>details.push([record.id,metric.number,metric.metric,component||'value',typeof value==='number'?value:null,value===null?'Unavailable':typeof value==='number'?'':String(value),unit(metric.number,component,value)]));
detail.getRange('A1:G1').values=[['Model','Metric no.','Metric','Component','Numeric value','Text or status','Unit']];
detail.getRangeByIndexes(1,0,details.length,7).values=details.map(row=>row.map(literal));
detail.getRange(`A1:G${details.length+1}`).format.font={name:'Arial',size:10,color:colors.ink};
detail.getRange('A1:G1').format={fill:colors.navy,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',verticalAlignment:'center',rowHeight:30};
detail.getRange(`A2:G${details.length+1}`).format.rowHeight=30;
for(const [range,width] of [['A1:A2',16],['B1:B2',10],['C1:C2',44],['D1:D2',60],['E1:E2',20],['F1:F2',78],['G1:G2',14]])detail.getRange(range).format.columnWidth=width;
detail.getRange(`C2:D${details.length+1}`).format.wrapText=true;detail.getRange(`F2:F${details.length+1}`).format.wrapText=true;
for(let i=0;i<details.length;i++){
 const height=Math.max(30,Math.ceil(String(details[i][3]).length/55)*13+8,Math.ceil(String(details[i][5]).length/70)*13+8);
 if(height>30)detail.getRange(`A${i+2}:G${i+2}`).format.rowHeight=height;
}
detail.getRange(`E2:E${details.length+1}`).setNumberFormat('General');
for(let i=0;i<details.length;i++)if(details[i][6]==='proportion')detail.getRange(`E${i+2}`).setNumberFormat('0.0%');
detail.getRange(`A1:G${details.length+1}`).format.verticalAlignment='center';
detail.tables.add(`A1:G${details.length+1}`,true,'MetricComponents');detail.freezePanes.freezeRows(1);detail.freezePanes.freezeColumns(2);
wb.recalculate();
await fs.mkdir(outputDir,{recursive:true});
const inspect=await wb.inspect({kind:'table',range:'Comparison!A6:G12',include:'values,formulas',tableMaxRows:7,tableMaxCols:7,maxChars:3000});
await fs.writeFile(path.join(outputDir,'inspection.ndjson'),inspect.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},maxChars:2000});
await fs.writeFile(path.join(outputDir,'formula-errors.ndjson'),errors.ndjson);
for(const [sheetName,range,file] of [['Comparison','A1:G16','comparison-preview.png'],['Comparison','A17:G25','comparison-bottom.png'],['Metric details','A1:G12','details-preview.png']]){
 const image=await wb.render({sheetName,range,scale:1,format:'png'});await fs.writeFile(path.join(outputDir,file),new Uint8Array(await image.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(path.join(outputDir,'ai431-full-model-comparison.xlsx'));
console.log(JSON.stringify({workbook:path.join(outputDir,'ai431-full-model-comparison.xlsx'),metrics:19,modelColumns:5,detailRows:details.length}));
