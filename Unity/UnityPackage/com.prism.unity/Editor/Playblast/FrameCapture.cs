using System.IO;
using UnityEngine;
using UnityEngine.Rendering;

namespace Prism.Unity.Editor
{
    /// <summary>Renders one camera frame into a PNG, in edit mode, without the Recorder package.</summary>
    public static class FrameCapture
    {
        public static void CaptureFrame(Camera cam, int width, int height, string pngPath)
        {
            if (cam == null) throw new PrismCommandException(ErrorCodes.BadArgs, "No camera to capture from.");
            if (width <= 0 || height <= 0 || width > 8192 || height > 8192)
                throw new PrismCommandException(ErrorCodes.BadArgs, $"Invalid resolution {width}x{height}.");

            var rt = RenderTexture.GetTemporary(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            var previousActive = RenderTexture.active;
            var previousTarget = cam.targetTexture;
            var previousAspect = cam.aspect;
            var tex = new Texture2D(width, height, TextureFormat.RGB24, false);
            try
            {
                cam.aspect = (float)width / height;
                var request = new RenderPipeline.StandardRequest { destination = rt };
                if (RenderPipeline.SupportsRenderRequest(cam, request))
                {
                    RenderPipeline.SubmitRenderRequest(cam, request);
                }
                else
                {
                    cam.targetTexture = rt;
                    cam.Render();
                }
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                tex.Apply();
                Directory.CreateDirectory(Path.GetDirectoryName(pngPath));
                File.WriteAllBytes(pngPath, tex.EncodeToPNG());
            }
            finally
            {
                cam.targetTexture = previousTarget;
                cam.aspect = previousAspect;
                RenderTexture.active = previousActive;
                RenderTexture.ReleaseTemporary(rt);
                Object.DestroyImmediate(tex);
            }
        }
    }
}
