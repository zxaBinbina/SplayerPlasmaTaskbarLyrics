#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Verify sidebar locale, unavailable theme feedback and native AGPL license view."""
import os,sys,time,json
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
os.environ.setdefault("QT_QUICK_BACKEND","software")
from PySide6.QtCore import QObject,Slot,QUrl,QPointF,QPoint,Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickItem,QQuickWindow
from PySide6.QtQml import QQmlEngine,QQmlComponent,QQmlExpression
from PySide6.QtTest import QTest
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/"helper"))
from sptl.server import BridgeServer
import threading
class Environment:
    running=False
    locale="zh-CN"
    theme={"available":False,"source":"cover"}
    favorite={"available":False,"liked":False}
    def refresh(self):pass
    def local_cover(self,cover):return None
server=BridgeServer(("127.0.0.1",0),environment=Environment())
worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
ui=(root/"dist/plasma6/org.kde.plasma.sptl/contents/ui")
app=QGuiApplication([]);engine=QQmlEngine();warnings=[]
engine.warnings.connect(lambda entries:warnings.extend(e.toString() for e in entries))
class Translations(QObject):
    @Slot(str,result=str)
    def i18n(self,text):return text
    @Slot(str,str,result=str)
    def i18nc(self,context,text):return text
    @Slot(str,str,str,result=str)
    @Slot(str,str,str,str,result=str)
    def i18ndc(self,domain,context,text,arg=""):return text.replace("%1",arg)
tr=Translations();engine.rootContext().setContextObject(tr)
def pump(ms=200):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end:app.processEvents();time.sleep(.005)
def expr(obj,text):
    q=QQmlExpression(engine.rootContext(),obj,text);r=q.evaluate()
    assert not q.hasError(),q.error().toString()
    return r[0] if isinstance(r,tuple) else r
component=QQmlComponent(engine)
component.setData(f'''import QtQuick 2.15
import QtQuick.Window 2.15
Window {{ width:780; height:900; visible:true
 Item {{ id:host;objectName:"owner";anchors.fill:parent;property var currentConfigPage:null
  Loader {{ objectName:"settingsLoader";anchors.fill:parent;source:"{(ui/"ConfigGeneral.qml").as_uri()}"; onLoaded:item.endpoint="http://127.0.0.1:{server.server_address[1]}" }}
 }}
}}'''.encode(),QUrl("file:///tmp/sptl-config-review.qml"))
window=component.create();assert window,"\n".join(e.toString() for e in component.errors())
pump(800)
owner=window.findChild(QObject,"owner");loader=window.findChild(QObject,"settingsLoader");settings=loader.property("item")
assert owner.findChild(QObject,"sptlNativeLicenseBinding"),"native license binding missing"
warning=settings.findChild(QObject,"spThemeWarning")
expr(settings,'edits=Object.assign({},edits,{themeMode:"splayer"})')
pump(100);assert warning.property("visible"),"missing SP theme warning"
def visualFind(item,name):
    if item.objectName()==name:return item
    for child in item.childItems():
        found=visualFind(child,name)
        if found:return found
themeEditor=visualFind(settings,"setting_themeMode")
manualEditor=visualFind(settings,"setting_manualDark")
assert themeEditor and manualEditor
themeBottom=themeEditor.mapToScene(QPointF(0,themeEditor.property("height"))).y()
warningTop=warning.mapToScene(QPointF(0,0)).y()
warningBottom=warning.mapToScene(QPointF(0,warning.property("height"))).y()
manualTop=manualEditor.mapToScene(QPointF(0,0)).y()
assert themeBottom <= warningTop < warningBottom <= manualTop,"warning must be directly below the theme source editor"
Environment.theme={"available":True,"mode":"light","accent":"#abcdef"}
pump(2100)
assert not warning.property("visible"),"warning must disappear when SP theme becomes available"
bridge=next(item for item in settings.children() if item.property("endpoint"))
bridge.setProperty("reachable",False)
assert warning.property("visible"),"lost bridge connection must warn about SP theme fallback"
assert bridge.property("plasmaTheme")
bridge.setProperty("reachable",True)
expr(settings,'edits=Object.assign({},edits,{themeMode:"plasma"})')
pump(100);assert not warning.property("visible"),"unexpected warning for Plasma theme"
print("Theme warning follows the selected source")
modelComponent=QQmlComponent(engine,QUrl.fromLocalFile(str(root/"dist/plasma6/org.kde.plasma.sptl/contents/config/config.qml")))
model=modelComponent.create();assert model,"\n".join(e.toString() for e in modelComponent.errors())
expr(model,'languageBridge.content=Object.assign({},languageBridge.content,{locale:"zh-CN"})')
assert expr(model,'get(0).name')=="设置"
expr(model,'languageBridge.content=Object.assign({},languageBridge.content,{locale:"en-US"})')
assert expr(model,'get(0).name')=="Settings"
print("Settings sidebar switches between Chinese and English")
loader.setProperty("active",False);pump(100)
aboutComponent=QQmlComponent(engine,QUrl.fromLocalFile("/usr/share/plasma/shells/org.kde.plasma.desktop/contents/configuration/AboutPlugin.qml"))
metadata={"pluginId":"org.kde.plasma.sptl","iconName":"application-x-plasma","name":"SPTL","version":"1.1.0","description":"Lyrics","website":"https://example.com","bugReportUrl":"","copyrightText":"","license":"AGPL-3.0-only","licenseText":"No license specified","authors":[],"otherContributors":[],"translators":[]}
about=aboutComponent.createWithInitialProperties({"metaData":metadata})
assert about,"\n".join(e.toString() for e in aboutComponent.errors())
about.setParent(owner);about.setParentItem(owner);about.setProperty("width",780);about.setProperty("height",850)
owner.setProperty("currentConfigPage",about);pump(300)
licenseText=(root/"LICENSE").read_text()
current=about.property("metaData");current=current.toVariant() if hasattr(current,"toVariant") else current
assert current["licenseText"]==licenseText,"license did not survive settings page replacement"
buttons=[i for i in about.findChildren(QQuickItem) if i.property("text")=="Read License" and i.property("hoverEnabled") is not None]
assert buttons,"native Read License button missing"
button=buttons[0];pos=button.mapToScene(QPointF(button.property("width")/2,button.property("height")/2))
QTest.mouseClick(window,Qt.LeftButton,pos=QPoint(round(pos.x()),round(pos.y())))
pump(400)
labels=[i for i in window.findChildren(QObject) if i.property("text")==licenseText]
assert labels,"native license sheet did not display the full AGPL text"
assert current["license"]=="AGPL-3.0-only"
print("Native About button displays full AGPL text and preserves the SPDX identifier")
unexpected=[entry for entry in warnings if not ("OverlaySheet.qml" in entry and "shortHeaderMargins" in entry)]
assert not unexpected,"\n".join(unexpected)
window.close();window.deleteLater();model.deleteLater();pump(50)
server.shutdown();server.server_close();worker.join()
