import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const [input,out]=process.argv.slice(2);
if(!input||!out)throw Error('usage: builder comparison.json output_dir');
const data=JSON.parse(await fs.readFile(input,'utf8'));
if(data.records.length!==13||data.table_rows.length!==19)throw Error('Expected all retained endpoints and nineteen metrics');
const wb=Workbook.create();const ink='#172B4D',navy='#243B53',muted='#526777',light='#F0F4F8';
const literal=x=>typeof x==='string'&&x.startsWith('=')?"'"+x:x;
const render=[];
for(const architecture of ['gxp','ai431']){
 const indices=data.records.map((r,i)=>r.architecture_group===architecture?i:-1).filter(i=>i>=0);
 const sheetName=architecture==='gxp'?'GxP results':'AI-431 results';const s=wb.worksheets.add(sheetName);s.showGridLines=false;
 const last=String.fromCharCode(66+indices.length);const scope=`A1:${last}25`;
 s.getRange(scope).format.font={name:'Arial',size:10,color:ink};
 s.getRange('A2').values=[[architecture==='gxp'?'GxP — historical and new attempts':'AI-431 — historical and new attempts']];s.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:navy};
 s.getRange('A3').values=[['All failures retained; nonconcurrent exploratory attempts; no matched superiority inference.']];s.getRange('A3').format.font={name:'Arial',size:10,color:muted};
 s.getRange('A4').values=[['Source: https://github.com/lyc0603/clinical_bench/tree/main/pre_experiment/results/architecture-followups-2026-11-08']];s.getRange('A4').format.font={name:'Arial',size:10,italic:true,color:muted};
 s.getRange(`A6:${last}6`).values=[['No.','Metric',...indices.map(i=>data.records[i].label)]];
 const rows=data.table_rows.map(r=>[r[0],r[1],...indices.map(i=>literal(r[i+2]))]);
 for(let c=0;c<indices.length;c++){
  const r=data.records[indices[c]];
  const minutes=r.metrics[14].value;if(typeof minutes==='number')rows[14][c+2]=minutes;
  const p21=r.metrics[3].value;const count=p21?.posthoc_terminal_dataset_rule_pairs??p21?.final_primary_dataset_rule_pairs;if(typeof count==='number')rows[3][c+2]=count;
 }
 s.getRange(`A7:${last}25`).values=rows;
 s.getRange(`A6:${last}6`).format={fill:navy,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:80,wrapText:true,verticalAlignment:'center'};
 s.getRange(`A7:${last}25`).format={wrapText:true,verticalAlignment:'center',rowHeight:48};
 s.getRange('A6:A25').format.columnWidth=5;s.getRange('B6:B25').format.columnWidth=43;s.getRange(`C6:${last}25`).format.columnWidth=42;
 for(let row=7;row<=25;row++)if(row%2===1)s.getRange(`A${row}:${last}${row}`).format.fill=light;
 for(const [row,height] of [[12,100],[14,76],[16,150],[17,78],[20,80],[21,65],[25,170]])s.getRange(`A${row}:${last}${row}`).format.rowHeight=height;
 s.getRange(`C10:${last}10`).format.horizontalAlignment='center';s.getRange(`C21:${last}21`).format.horizontalAlignment='center';
 s.getRange(`C21:${last}21`).setNumberFormat('0.00');s.getRange('A7:A25').setNumberFormat('0');
 s.freezePanes.freezeRows(6);s.freezePanes.freezeColumns(2);
 render.push([sheetName,`A1:${last}16`,architecture+'-top.png'],[sheetName,`A17:${last}25`,architecture+'-bottom.png']);
}
const detail=wb.worksheets.add('Metric details');detail.showGridLines=false;
const rows=[];
function leaves(value,prefix,fn){if(value!==null&&typeof value==='object'){const entries=Object.entries(value);if(!entries.length)fn(prefix,null);for(const [k,v] of entries)leaves(v,prefix?prefix+'.'+k:k,fn);}else fn(prefix,value);}
function unit(n,k,v){if(typeof v!=='number')return '';if(k.endsWith('rate'))return 'proportion';if(k.includes('seconds'))return 'seconds';if(n===15)return 'minutes';if(k.includes('tokens'))return 'tokens';if(n===17)return 'datasets';if(n===18)return 'variables';return 'count';}
for(const r of data.records)for(const m of r.metrics)leaves(m.value,'',(key,value)=>rows.push([r.id,r.architecture_group,m.number,m.metric,key||'value',typeof value==='number'?value:null,value===null?'Unavailable':typeof value==='number'?'':String(value),unit(m.number,key,value)]));
detail.getRange('A1:H1').values=[['Attempt','Architecture','Metric no.','Metric','Component','Numeric value','Text or status','Unit']];detail.getRangeByIndexes(1,0,rows.length,8).values=rows.map(r=>r.map(literal));
detail.getRange(`A1:H${rows.length+1}`).format={font:{name:'Arial',size:10,color:ink},verticalAlignment:'center',rowHeight:32};
detail.getRange('A1:H1').format={fill:navy,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:32};
for(const [col,width] of [['A',35],['B',14],['C',11],['D',44],['E',62],['F',22],['G',85],['H',16]])detail.getRange(`${col}1:${col}2`).format.columnWidth=width;
detail.getRange(`A2:A${rows.length+1}`).format.wrapText=true;detail.getRange(`D2:E${rows.length+1}`).format.wrapText=true;detail.getRange(`G2:G${rows.length+1}`).format.wrapText=true;
for(let i=0;i<rows.length;i++){
 const h=Math.max(32,Math.ceil(rows[i][0].length/31)*13+8,Math.ceil(rows[i][4].length/57)*13+8,Math.ceil(rows[i][6].length/76)*13+8);detail.getRange(`A${i+2}:H${i+2}`).format.rowHeight=h;
 if(rows[i][7]==='proportion')detail.getRange(`F${i+2}`).setNumberFormat('0.0%');
}
detail.tables.add(`A1:H${rows.length+1}`,true,'AllMetricComponents');detail.freezePanes.freezeRows(1);detail.freezePanes.freezeColumns(2);render.push(['Metric details','A1:H12','details.png']);
wb.recalculate();await fs.mkdir(out,{recursive:true});
for(const [sheetName,range,file] of render){const blob=await wb.render({sheetName,range,scale:1,format:'png'});await fs.writeFile(path.join(out,file),new Uint8Array(await blob.arrayBuffer()));}
const check=await wb.inspect({kind:'table',range:'AI-431 results!A6:I8',include:'values,formulas',tableMaxRows:3,tableMaxCols:9,maxChars:3000});await fs.writeFile(path.join(out,'inspection.ndjson'),check.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},maxChars:2000});await fs.writeFile(path.join(out,'formula-errors.ndjson'),errors.ndjson);
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(path.join(out,'architecture-followups.xlsx'));console.log(JSON.stringify({endpoints:data.records.length,metrics:19,detailRows:rows.length,workbook:path.join(out,'architecture-followups.xlsx')}));
