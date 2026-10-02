using System;
using System.IO;
using CCL.Types.Proxies.Controls;
using CCL.Types.Proxies.Indicators;
using UnityEngine;

public static partial class CclLocoBuild
{
    // These independent brake/speed faces are app artwork, not pieces cut from a DV cab atlas.
    // The numerical face range and the actual indicator range are configured together.
    static readonly string[] GaugeLetters = {
        "01110100011000111111100011000110001", // A
        "11110100011000111110100011000111110", // B
        "01111100001000010000100001000001111", // C
        "11111100001000011110100001000011111", // E
        "10001100101010011000101001001010001", // K
        "10000100001000010000100001000011111", // L
        "10001110111010110101100011000110001", // M
        "11110100011000111110100001000010000", // P
        "11110100011000111110101001001010001", // R
        "01111100001000001110000010000111110", // S
        "11111001000010000100001000010000100", // T
        "10001100011000101110001000010000100", // Y
        "10001100011000111111100011000110001", // H
        "00001000100001000100010000100010000", // /
        "01110100010000100010001000000000100", // ?
        "11111001000010000100001000010011111"  // I
    };
    const string GaugeAlphabet = "ABCEKLMPRSTYH/?I";

    static void GaugeText(Texture2D texture, string text, float u, float v, int pixel, Color ink)
    {
        int width=(text.Length*6-1)*pixel, left=(int)(u*texture.width)-width/2, top=(int)(v*texture.height)+7*pixel/2;
        for(int i=0;i<text.Length;i++) {
            int index=GaugeAlphabet.IndexOf(text[i]); if(index<0) continue;
            var glyph=GaugeLetters[index];
            for(int y=0;y<7;y++) for(int x=0;x<5;x++) if(glyph[y*5+x]=='1')
                for(int py=0;py<pixel;py++) for(int px=0;px<pixel;px++)
                    texture.SetPixel(left+(i*6+x)*pixel+px,top-y*pixel-py,ink);
        }
    }

    static Material Rr2dvGaugeFaceMaterial(string reading)
    {
        string key="rr2dv_face_"+reading;
        if(ownMats.ContainsKey(key)) return ownMats[key];
        var face=Dial(0,reading=="speed"?100:10,reading=="speed"?20:2,reading=="speed"?5:.5f,false);
        var ink=new Color(.06f,.06f,.06f);
        GaugeText(face,reading=="speed"?"KM/H":"BAR",.5f,.40f,3,ink);
        if(reading=="brake") {
            GaugeText(face,"PIPE",.5f,.31f,3,ink);
            GaugeText(face,"CYL",.5f,.24f,3,new Color(.7f,.05f,.03f));
        }
        face.Apply(); return ownMats[key]=TexMat(key,face);
    }

    static void Rr2dvGaugeCaption(Transform gauge, string title)
    {
        var texture=new Texture2D(256,64,TextureFormat.RGBA32,false);
        var pixels=new Color[256*64]; for(int i=0;i<pixels.Length;i++) pixels[i]=new Color(.035f,.035f,.035f);
        texture.SetPixels(pixels); GaugeText(texture,title,.5f,.5f,5,new Color(.9f,.85f,.7f)); texture.Apply();
        string key="rr2dv_caption_"+title.Replace('/','_');
        if(!ownMats.ContainsKey(key)) ownMats[key]=TexMat(key,texture);
        else UnityEngine.Object.DestroyImmediate(texture);
        var plate=Child(gauge,"reading label",new Vector3(0,-.084f,-.061f));
        plate.localRotation=Quaternion.Euler(0,180,0); plate.localScale=new Vector3(.082f,.020f,1);
        // A rectangular label uses its own mesh so no dynamic font/material resources are needed in game.
        var mesh=new Mesh {name=key};
        mesh.vertices=new[]{new Vector3(-.5f,-.5f,0),new Vector3(.5f,-.5f,0),new Vector3(.5f,.5f,0),new Vector3(-.5f,.5f,0)};
        mesh.triangles=new[]{0,1,2,0,2,3}; mesh.uv=new[]{Vector2.right,Vector2.zero,Vector2.up,Vector2.one};mesh.RecalculateNormals();
        plate.gameObject.AddComponent<MeshFilter>().sharedMesh=SaveMesh(mesh,key);
        plate.gameObject.AddComponent<MeshRenderer>().sharedMaterial=ownMats[key];
    }

    static void BuildRr2dvStandaloneGauge(Transform gauge, string reading, LocoIndicatorReaderProxy hud)
    {
        if(reading!="brake" && reading!="speed") throw new InvalidDataException("Unsupported standalone gauge reading: "+reading);
        S060GaugePart(gauge,"housing","s060_gauge_pressuremeter","LocoS060_Interior",Vector3.zero);
        S060GaugePart(gauge,"glass","s060_gauge_glass_pressuremeter","GlassIndoors",Vector3.zero);
        var face=Child(gauge,"face",new Vector3(0,0,-.0284f));
        face.localRotation=Quaternion.Euler(0,180,0);face.localScale=Vector3.one*.152f;
        face.gameObject.AddComponent<MeshFilter>().sharedMesh=discMesh;
        face.gameObject.AddComponent<MeshRenderer>().sharedMaterial=Rr2dvGaugeFaceMaterial(reading);
        // Keep the core's tested two-needle construction, separating pipe and application readers.
        var needles=Child(gauge,"needles",new Vector3(0,0,-.0284f)); needles.localRotation=Quaternion.Euler(0,180,0);
        if(reading=="brake") {
            // DV brake readers pass absolute pressure directly: released = 1 bar, printed zero.
            var cylinder=GaugeNeedle(needles,"needle cylinder",.152f,1,11,"needle_red",.0015f);
            Add(cylinder.gameObject,"CCL.Types.Proxies.Indicators.IndicatorBrakeCylinderReaderProxy");
            hud.brakeCylinder=cylinder.GetComponent<IndicatorGaugeProxy>();
            var pipe=GaugeNeedle(needles,"needle pipe",.152f,1,11,"needle_black",.003f);
            Add(pipe.gameObject,"CCL.Types.Proxies.Indicators.IndicatorBrakePipeReaderProxy");
            hud.brakePipe=pipe.GetComponent<IndicatorGaugeProxy>();
            Rr2dvGaugeCaption(gauge,"BRAKE");
        } else {
            var speed=GaugeNeedle(needles,"needle speed",.152f,0,100,"needle_black",.002f);
            var reader=speed.gameObject.AddComponent<IndicatorPortReaderProxy>();
            reader.portId="traction.WHEEL_SPEED_KMH_EXT_IN";reader.valueMultiplier=1;reader.useAbsoluteValue=true;
            hud.speed=Rr2dvLaggingGauge(speed.GetComponent<IndicatorGaugeProxy>());
            Rr2dvGaugeCaption(gauge,"KM/H");
        }
    }
}
