from krita import Krita, Extension, Scratchpad, ManagedColor, Preset
from PyQt5.QtCore import QTimer, QEvent, QPointF, Qt
from PyQt5.QtGui import QColor, QTabletEvent, QImage
from PyQt5.QtWidgets import QApplication, QWidget
from pathlib import Path
import os, traceback, math, json

ROOT = Path(os.environ['TSP_BUILD_DIR'])
OUT = Path(os.environ['TSP_TEST_OUTPUT'])
OUT.mkdir(exist_ok=True)
PREVIEWS = OUT/'strokes'
PREVIEWS.mkdir(parents=True,exist_ok=True)

def log(s):
    with (OUT/'log.txt').open('a') as f:
        f.write(str(s)+'\n')

class PencilTest(Extension):
    def setup(self):
        self.done = False
        Krita.instance().notifier().windowCreated.connect(self.schedule)

    def createActions(self, window):
        pass

    def schedule(self):
        if not self.done:
            self.done = True
            QTimer.singleShot(1200, self.start)

    def start(self):
        try:
            app = Krita.instance()
            self.report = {'krita_version':app.version(),'presets':[]}
            self.doc = app.createDocument(1100, 450, 'Brush verification', 'RGBA', 'U8', '', 100.0)
            app.activeWindow().addView(self.doc)
            self.view = app.activeWindow().activeView()
            self.view.setForeGroundColor(ManagedColor.fromQColor(QColor('#252527')))
            self.presets = {k:v for k,v in app.resources('preset').items() if k.startswith('TSP ')}
            log('Loaded custom presets: '+str(sorted(self.presets)))
            assert len(self.presets)==10, 'All ten presets must load from bundle'
            self.catalog = json.loads((ROOT/'brush_catalog.json').read_text())
            self.pad = Scratchpad(self.view, QColor('white'))
            self.pad.linkCanvasZoom(False)
            self.pad.resize(1122,472)
            self.pad.show()
            QApplication.processEvents()
            self.target = next(w for w in self.pad.findChildren(QWidget) if w.metaObject().className()=='KisScratchPad')
            self.index = 0
            self.timestamp = 10
            self.next_brush()
        except Exception:
            self.fail()

    def fail(self):
        log(traceback.format_exc())
        os._exit(1)

    def blank(self):
        image = QImage(1100,450,QImage.Format_ARGB32)
        image.fill(QColor('#fefefe'))
        self.pad.loadScratchpadImage(image)

    def stroke(self, points, pressure=lambda t:.75, tilt=lambda t:(0,0)):
        for i,(x,y) in enumerate(points):
            t=i/(len(points)-1)
            kind = QEvent.TabletPress if i==0 else QEvent.TabletRelease if i==len(points)-1 else QEvent.TabletMove
            button=Qt.LeftButton if i in (0,len(points)-1) else Qt.NoButton
            buttons=Qt.NoButton if i==len(points)-1 else Qt.LeftButton
            pos=QPointF(x,y)
            xt,yt=tilt(t)
            event=QTabletEvent(kind,pos,QPointF(self.target.mapToGlobal(pos.toPoint())),QTabletEvent.Stylus,
                               QTabletEvent.Pen,pressure(t) if i<len(points)-1 else 0.,int(xt),int(yt),
                               0.,0.,0,Qt.NoModifier,123456,button,buttons)
            event.setTimestamp(self.timestamp)
            self.timestamp+=8
            QApplication.sendEvent(self.target,event)

    def line(self,x1,x2,y,pressure=.75,tilt=(0,0)):
        points=[(x1+(x2-x1)*i/160,y) for i in range(161)]
        self.stroke(points,lambda t:pressure,lambda t:tilt)

    def next_brush(self):
        try:
            if self.index==len(self.catalog):
                (OUT/'runtime_report.json').write_text(json.dumps(self.report,indent=2))
                log('Validation finished')
                os._exit(0)
            self.spec=self.catalog[self.index]
            resource=self.presets[self.spec['preset_name']]
            self.view.setCurrentBrushPreset(resource)
            QApplication.processEvents()
            xml=Preset(resource).toXML()
            (OUT/f"{self.spec['id']:02}-loaded.xml").write_text(xml)
            self.report['presets'].append({'name':resource.name(),'filename':resource.filename(),
                                           'loaded_size':self.view.brushSize(),
                                           'opacity':self.view.paintingOpacity(),
                                           'flow':self.view.paintingFlow()})
            self.blank()
            self.stroke([(35+360*i/300,64+14*math.sin(i/300*math.pi*2)) for i in range(301)],
                        lambda t:.08+.92*t)
            self.stroke([(460+390*i/300,64+9*math.sin(i/300*math.pi*2)) for i in range(301)],
                        lambda t:.72,lambda t:(0,55*t))
            self.line(45,300,190,.40,(0,55))
            self.line(365,620,190,.85,(0,55))
            for i in range(9):
                self.stroke([(690+18*i+22*t/45,215-58*t/45) for t in range(46)],lambda t:.5+.35*t)
            QTimer.singleShot(550,self.save_preview)
        except Exception:
            self.fail()

    def save_preview(self):
        try:
            self.pad.copyScratchpadImageData().copy(0,0,900,260).save(str(PREVIEWS/f"{self.spec['id']:02}.png"))
            self.blank()
            self.line(40,200,100,.75,(0,0))
            self.line(290,450,100,.75,(0,55))
            self.line(540,700,100,.75,(55,0))
            self.line(790,950,100,.20,(0,0))
            QTimer.singleShot(400,self.save_metrics)
        except Exception:
            self.fail()

    def save_metrics(self):
        try:
            self.pad.copyScratchpadImageData().save(str(OUT/f"{self.spec['id']:02}-metrics.png"))
            log('Rendered '+self.spec['preset_name'])
            self.index+=1
            self.next_brush()
        except Exception:
            self.fail()

Krita.instance().addExtension(PencilTest(Krita.instance()))
