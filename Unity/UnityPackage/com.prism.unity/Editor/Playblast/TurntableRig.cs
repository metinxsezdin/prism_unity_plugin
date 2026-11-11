using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Prism.Unity.Editor
{
    /// <summary>
    /// A temporary turntable: clones of the targets in an isolated preview scene, with a camera
    /// orbiting them and three lights that move with the camera. The user's scene and the targets
    /// are never touched; Dispose removes everything.
    /// </summary>
    public sealed class TurntableRig : IDisposable
    {
        public const string ObjectPrefix = "__PrismTurntable";
        public static readonly Color Background = new Color(0.18f, 0.18f, 0.2f, 1f);
        const float FieldOfView = 30f;
        const float Elevation = 15f;

        Scene _scene;
        readonly GameObject _root;
        readonly Vector3 _center;
        readonly float _distance;

        public Camera Camera { get; }

        public TurntableRig(IReadOnlyList<GameObject> targets, int width, int height)
        {
            if (targets == null || targets.Count == 0 || targets.Any(t => t == null))
                throw new PrismCommandException(ErrorCodes.BadArgs, "Select at least one object for the turntable.");

            _scene = EditorSceneManager.NewPreviewScene();
            try
            {
                _root = new GameObject(ObjectPrefix);
                SceneManager.MoveGameObjectToScene(_root, _scene);
                foreach (var target in targets)
                {
                    var clone = UnityEngine.Object.Instantiate(target, target.transform.position, target.transform.rotation);
                    clone.name = ObjectPrefix + "_" + target.name;
                    clone.transform.localScale = target.transform.lossyScale;
                    SceneManager.MoveGameObjectToScene(clone, _scene);
                    clone.transform.SetParent(_root.transform, true);
                }

                var bounds = Bounds(_root);
                _center = bounds.center;
                var radius = Mathf.Max(bounds.extents.magnitude, 0.01f);
                _distance = radius / Mathf.Sin(FieldOfView * 0.5f * Mathf.Deg2Rad) * 1.1f;

                var camGo = new GameObject(ObjectPrefix + "_Camera");
                SceneManager.MoveGameObjectToScene(camGo, _scene);
                camGo.transform.SetParent(_root.transform, false);
                Camera = camGo.AddComponent<Camera>();
                Camera.scene = _scene;
                Camera.cameraType = CameraType.Preview;
                Camera.clearFlags = CameraClearFlags.SolidColor;
                Camera.backgroundColor = Background;
                Camera.fieldOfView = FieldOfView;
                Camera.nearClipPlane = Mathf.Max(0.01f, _distance - radius * 2f);
                Camera.farClipPlane = _distance + radius * 4f;
                Camera.aspect = (float)width / Mathf.Max(1, height);

                AddLight("Key", new Vector3(35, -40, 0), 1.2f);
                AddLight("Fill", new Vector3(15, 50, 0), 0.5f);
                AddLight("Rim", new Vector3(160, 0, 0), 0.8f);
                SetAngle(0);
            }
            catch
            {
                Dispose();
                throw;
            }
        }

        void AddLight(string name, Vector3 localEuler, float intensity)
        {
            var go = new GameObject($"{ObjectPrefix}_{name}Light");
            SceneManager.MoveGameObjectToScene(go, _scene);
            go.transform.SetParent(Camera.transform, false);
            go.transform.localRotation = Quaternion.Euler(localEuler);
            var light = go.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = intensity;
        }

        /// <summary>Place the camera at this orbit angle (degrees) around the targets.</summary>
        public void SetAngle(float degrees)
        {
            var offset = Quaternion.Euler(Elevation, degrees, 0f) * (Vector3.back * _distance);
            Camera.transform.position = _center + offset;
            Camera.transform.LookAt(_center);
        }

        static Bounds Bounds(GameObject root)
        {
            var renderers = root.GetComponentsInChildren<Renderer>(true);
            if (renderers.Length == 0)
                throw new PrismCommandException(ErrorCodes.BadArgs, "The selected objects have nothing visible to render.");
            var b = renderers[0].bounds;
            foreach (var r in renderers.Skip(1)) b.Encapsulate(r.bounds);
            return b;
        }

        public void Dispose()
        {
            if (_scene.IsValid())
                EditorSceneManager.ClosePreviewScene(_scene); // destroys every object in it
        }
    }
}
