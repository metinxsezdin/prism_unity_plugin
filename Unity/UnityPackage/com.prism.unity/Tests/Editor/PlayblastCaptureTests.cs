using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Prism.Unity.Editor.Tests
{
    public class PlayblastCaptureTests
    {
        const string SceneFolder = "Assets/PrismTestScenes";
        string _outDir;

        [SetUp]
        public void SetUp()
        {
            _outDir = Path.Combine(PrismSettings.ProjectRoot, "Temp", "PrismUnityTests", "frames", Path.GetRandomFileName());
            Directory.CreateDirectory(_outDir);
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        }

        [TearDown]
        public void TearDown()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            AssetDatabase.DeleteAsset(SceneFolder);
            if (Directory.Exists(_outDir)) Directory.Delete(_outDir, true);
        }

        static Texture2D LoadPng(string path)
        {
            var tex = new Texture2D(2, 2);
            tex.LoadImage(File.ReadAllBytes(path));
            return tex;
        }

        static GameObject Cube(string name = "Target")
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.position = new Vector3(5, 1, -2);
            go.transform.rotation = Quaternion.Euler(0, 30, 0);
            return go;
        }

        static int RigObjectCount() =>
            Resources.FindObjectsOfTypeAll<GameObject>().Count(g => g.name.StartsWith(TurntableRig.ObjectPrefix));

        [Test]
        public void CaptureWritesPngOfRequestedSize()
        {
            Cube();
            var camGo = new GameObject("Cam");
            var cam = camGo.AddComponent<Camera>();
            camGo.transform.position = new Vector3(5, 1, -6);
            var png = Path.Combine(_outDir, "frame.png");

            FrameCapture.CaptureFrame(cam, 512, 256, png);

            var tex = LoadPng(png);
            Assert.AreEqual(512, tex.width);
            Assert.AreEqual(256, tex.height);
        }

        [Test]
        public void FramesBoundsOfTargets()
        {
            var cube = Cube();
            using (var rig = new TurntableRig(new[] { cube }, 256, 256))
            {
                rig.SetAngle(0);
                var png = Path.Combine(_outDir, "turntable.png");
                FrameCapture.CaptureFrame(rig.Camera, 256, 256, png);
                var tex = LoadPng(png);
                var center = tex.GetPixel(128, 128);
                var corner = tex.GetPixel(2, 2);
                Assert.Greater(Mathf.Abs(center.grayscale - corner.grayscale) + Mathf.Abs(center.r - corner.r), 0.02f,
                    $"Center {center} looks like background {corner}: the target is not in frame.");
            }
        }

        [Test]
        public void TurntableShowsOnlyTargets()
        {
            var cube = Cube();
            var other = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            other.transform.position = cube.transform.position + Vector3.forward * 0.1f;
            other.transform.localScale = Vector3.one * 5; // would hide the cube if it were rendered
            using (var rig = new TurntableRig(new[] { cube }, 128, 128))
            {
                Assert.AreNotEqual(cube.scene, rig.Camera.gameObject.scene, "The rig must live in its own preview scene.");
                Assert.IsTrue(EditorSceneManager.IsPreviewScene(rig.Camera.gameObject.scene));
            }
        }

        [Test]
        public void TurntableDoesNotDirtySceneOrMoveTargets()
        {
            var cube = Cube();
            AssetDatabase.CreateFolder("Assets", "PrismTestScenes");
            var scene = EditorSceneManager.GetActiveScene();
            EditorSceneManager.SaveScene(scene, SceneFolder + "/turntable.unity");
            Assert.IsFalse(scene.isDirty);
            var pos = cube.transform.position;
            var rot = cube.transform.rotation;
            var scale = cube.transform.localScale;

            using (var rig = new TurntableRig(new[] { cube }, 128, 128))
            {
                foreach (var angle in new[] { 0f, 90f, 180f, 270f })
                {
                    rig.SetAngle(angle);
                    FrameCapture.CaptureFrame(rig.Camera, 128, 128, Path.Combine(_outDir, $"f{angle}.png"));
                }
            }

            Assert.IsFalse(EditorSceneManager.GetActiveScene().isDirty);
            Assert.AreEqual(pos, cube.transform.position);
            Assert.AreEqual(rot, cube.transform.rotation);
            Assert.AreEqual(scale, cube.transform.localScale);
            Assert.AreEqual(0, RigObjectCount(), "Temporary rig objects were left behind.");
            Assert.AreEqual(1, EditorSceneManager.GetActiveScene().rootCount);
        }

        [Test]
        public void TurntableCleansUpOnException()
        {
            var cube = Cube();
            Assert.Throws<System.InvalidOperationException>(() =>
            {
                using (var rig = new TurntableRig(new[] { cube }, 64, 64))
                {
                    rig.SetAngle(45);
                    throw new System.InvalidOperationException("boom");
                }
            });
            Assert.AreEqual(0, RigObjectCount());
        }

        [Test]
        public void AnglesProduceDifferentFrames()
        {
            var cube = Cube();
            using (var rig = new TurntableRig(new[] { cube }, 64, 64))
            {
                rig.SetAngle(0);
                FrameCapture.CaptureFrame(rig.Camera, 64, 64, Path.Combine(_outDir, "a.png"));
                rig.SetAngle(45);
                FrameCapture.CaptureFrame(rig.Camera, 64, 64, Path.Combine(_outDir, "b.png"));
            }
            CollectionAssert.AreNotEqual(File.ReadAllBytes(Path.Combine(_outDir, "a.png")), File.ReadAllBytes(Path.Combine(_outDir, "b.png")));
        }

        [Test]
        public void RejectsEmptyTargets()
        {
            Assert.Throws<PrismCommandException>(() => new TurntableRig(new GameObject[0], 64, 64));
        }
    }
}
