using System;
using System.Collections;
using System.Threading.Tasks;
using NUnit.Framework;

namespace Prism.Unity.Editor.Tests.Support
{
    internal static class E2EWait
    {
        /// <summary>Yield until the task completes; rethrow its exception so the test shows the bridge error.</summary>
        public static IEnumerator For(Task task, double timeoutSec)
        {
            var deadline = DateTime.UtcNow.AddSeconds(timeoutSec);
            while (!task.IsCompleted)
            {
                if (DateTime.UtcNow > deadline)
                    Assert.Fail($"Timed out after {timeoutSec} s.");
                yield return null;
            }
            if (task.IsFaulted)
            {
                var e = task.Exception.GetBaseException();
                if (e is PrismCommandException p)
                    Assert.Fail($"{p.Code}: {p.Message}\n{p.Details}");
                throw e;
            }
        }
    }
}
