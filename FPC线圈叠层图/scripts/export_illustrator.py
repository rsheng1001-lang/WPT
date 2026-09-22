"""Use the Illustrator skill bridge to deliver named native layers and exports."""
from pathlib import Path
import json
import sys
import argparse
import os
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser()
parser.add_argument('--output-dir',required=True)
parser.add_argument('--main-only',action='store_true')
parser.add_argument('--width-mm',type=float,help='Uniformly resize native artwork to this final width')
ARGS=parser.parse_args()
OUT=ROOT/ARGS.output_dir
SKILL=Path(os.environ.get('FPC_ILLUSTRATOR_SKILL',r'C:\Users\Liuxm\.zcode\skills\scientific-illustrator-agent'))
sys.path.insert(0,str(SKILL/'src'))
from illustrator.com_client import IllustratorClient,jsx_literal

reports=[]
jobs=[('WPT_Exploded_Refined','illustrator_main')]
if not ARGS.main_only: jobs.append(('WPT_Geometry_Details','illustrator_details'))
for stem,sub in jobs:
    for suffix in ('.ai','.png','.pdf'):
        if (OUT/(stem+suffix)).exists(): raise FileExistsError(OUT/(stem+suffix))
    root=ET.parse(OUT/(stem+'.svg')).getroot()
    names=[e.attrib['id'] for e in root if e.tag.endswith('}g')]
    source=OUT/sub/'progressive.ai'
    with IllustratorClient() as c:
        # Resolve only the source created by this workflow. Other documents stay open.
        init='''(function(p){
            var d=null; for(var i=0;i<app.documents.length;i++){
                try{if(app.documents[i].fullName.fsName===new File(p).fsName)d=app.documents[i];}catch(e){}
            }
            if(!d)d=app.open(new File(p)); $.global.FPC_V2_SOURCE=d;
            var b=d.artboards[0].artboardRect; return [b[2]-b[0],b[1]-b[3],d.pathItems.length,d.textFrames.length].join('|');
        })(DATA);'''.replace('DATA',jsx_literal(source.as_posix()))
        w,h,ep,et=map(float,c.execute_jsx(init,owned_document=False).split('|'))
        c.create_document(w,h)
        js='''(function(names){
            var d=app.activeDocument,s=$.global.FPC_V2_SOURCE;
            var sb=s.artboards[0].artboardRect,db=d.artboards[0].artboardRect,created=[];
            for(var i=0;i<names.length;i++){
                var L=i===0?d.layers[0]:d.layers.add(); L.name=names[i];
                var g=s.groupItems.getByName('SCIUNIT'+('00000'+i).slice(-5));
                var x=g.left-sb[0],y=g.top-sb[1];
                var a=g.duplicate(L,ElementPlacement.PLACEATBEGINNING);
                a.name=names[i];a.position=[db[0]+x,db[1]+y];
                created.push(a);
            }
            var targetWidth=TARGET_WIDTH;
            if(targetWidth>0){
                var factor=targetWidth/(db[2]-db[0]);
                for(var k=0;k<created.length;k++){
                    var item=created[k],px=item.left-db[0],py=item.top-db[1];
                    item.resize(factor*100,factor*100,true,true,true,true,factor*100,Transformation.TOPLEFT);
                    item.position=[db[0]+px*factor,db[1]+py*factor];
                }
                d.artboards[0].artboardRect=[db[0],db[1],db[0]+targetWidth,db[1]-(db[1]-db[3])*factor];
                db=d.artboards[0].artboardRect;
            }
            delete $.global.FPC_V2_SOURCE; app.redraw();
            var clipped=[];
            for(var j=0;j<d.textFrames.length;j++){
                var t=d.textFrames[j],b=t.visibleBounds;
                if(b[0]<db[0]||b[2]>db[2]||b[1]>db[1]||b[3]<db[3])clipped.push(t.contents);
            }
            return [d.pathItems.length,d.textFrames.length,d.rasterItems.length,d.placedItems.length,d.layers.length,clipped.join(';')].join('|');
        })(DATA);'''.replace('DATA',jsx_literal(names)).replace('TARGET_WIDTH',str(ARGS.width_mm*72/25.4 if ARGS.width_mm else 0))
        result=c.execute_jsx(js).split('|')
        assert int(result[0])==int(ep) and int(result[1])==int(et),result
        assert result[2:4]==['0','0'] and not result[5],result
        ai=OUT/(stem+'.ai')
        c.save_document(ai)
        png=OUT/(stem+'.png')
        pdf=OUT/(stem+'.pdf')
        script='''(function(p){
            var d=app.activeDocument, f=new File(p.png);if(f.exists)throw new Error('PNG exists');
            var o=new ExportOptionsPNG24();o.antiAliasing=true;o.transparency=false;o.artBoardClipping=true;
            o.horizontalScale=300;o.verticalScale=300;d.exportFile(f,ExportType.PNG24,o);
            f=new File(p.pdf);if(f.exists)throw new Error('PDF exists');
            var po=new PDFSaveOptions();po.preserveEditability=true;d.saveAs(f,po);
            var ao=new IllustratorSaveOptions();ao.pdfCompatible=true;d.saveAs(new File(p.ai),ao);
            return 'OK';
        })(DATA);'''.replace('DATA',jsx_literal(dict(png=png.as_posix(),pdf=pdf.as_posix(),ai=ai.as_posix())))
        assert c.execute_jsx(script)=='OK'
        report=dict(file=stem,paths=int(ep),texts=int(et),layers=names,raster=0,placed=0,clipped_text=0)
        if stem=='WPT_Exploded_Refined' and 'TOP_COVERLAY' in names:
            order=list(reversed(names))
            assert order.index('TOP_COMPONENTS')<order.index('TOP_COVERLAY')<order.index('L1_TOP_COPPER')
            assert order.index('L4_BOTTOM_COPPER')<order.index('BOTTOM_COVERLAY')<order.index('BOTTOM_COMPONENTS')
            report.update(coverlay_layers=2,coverlay_order_verified=True,reference_designators_drawn=False)
        reports.append(report)
        print(json.dumps(report))
(OUT/'illustrator_audit.json').write_text(json.dumps(reports,indent=2),'utf-8')
