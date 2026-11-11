using System.Collections;
using System.Threading;
using System.Threading.Tasks;
using NUnit.Framework;
using UnityEngine.TestTools;

namespace Prism.Unity.Editor.Tests
{
    public class MainThreadDispatcherTests
    {
        [UnityTest]
        public IEnumerator DeferRunsActionOnMainThread()
        {
            var mainId = Thread.CurrentThread.ManagedThreadId;
            var ranOn = -1;
            MainThreadDispatcher.Defer(() => ranOn = Thread.CurrentThread.ManagedThreadId);
            for (var i = 0; i < 50 && ranOn == -1; i++) yield return null;
            Assert.AreEqual(mainId, ranOn);
        }

        [UnityTest]
        public IEnumerator RunFromBackgroundThreadUsesMainThread()
        {
            var mainId = Thread.CurrentThread.ManagedThreadId;
            var task = Task.Run(() => MainThreadDispatcher.Run(() => Thread.CurrentThread.ManagedThreadId, System.TimeSpan.FromSeconds(10)));
            for (var i = 0; i < 200 && !task.IsCompleted; i++) yield return null;
            Assert.IsTrue(task.IsCompleted);
            Assert.AreEqual(mainId, task.Result);
        }

        [Test]
        public void MainThreadContextIsCaptured()
        {
            Assert.IsTrue(MainThreadDispatcher.HasMainThreadContext,
                "Without the main SynchronizationContext, work waits for EditorApplication.update, which barely ticks while Unity is in the background.");
        }
    }
}
