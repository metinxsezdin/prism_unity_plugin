using System;
using System.Collections.Concurrent;
using System.Threading;
using System.Threading.Tasks;
using UnityEditor;

namespace Prism.Unity.Editor
{
    /// <summary>Runs work on the editor's main thread, pumped by EditorApplication.update.</summary>
    [InitializeOnLoad]
    public static class MainThreadDispatcher
    {
        static readonly ConcurrentQueue<Action> Queue = new ConcurrentQueue<Action>();
        static readonly int MainThreadId;

        static MainThreadDispatcher()
        {
            MainThreadId = Thread.CurrentThread.ManagedThreadId;
            EditorApplication.update += Pump;
        }

        public static bool IsMainThread => Thread.CurrentThread.ManagedThreadId == MainThreadId;

        /// <summary>
        /// Queue fn for the main thread. The returned task faults with TimeoutException when
        /// fn has not finished within the timeout (fn itself still runs to completion).
        /// </summary>
        public static Task<T> Run<T>(Func<T> fn, TimeSpan timeout)
        {
            var tcs = new TaskCompletionSource<T>(TaskCreationOptions.RunContinuationsAsynchronously);
            if (IsMainThread)
            {
                try { tcs.SetResult(fn()); }
                catch (Exception e) { tcs.SetException(e); }
                return tcs.Task;
            }

            Queue.Enqueue(() =>
            {
                try { tcs.TrySetResult(fn()); }
                catch (Exception e) { tcs.TrySetException(e); }
            });
            return WithTimeout(tcs.Task, timeout);
        }

        static async Task<T> WithTimeout<T>(Task<T> task, TimeSpan timeout)
        {
            var finished = await Task.WhenAny(task, Task.Delay(timeout)).ConfigureAwait(false);
            if (finished != task)
                throw new TimeoutException($"Unity did not finish the command within {timeout.TotalSeconds:0.#} s.");
            return await task.ConfigureAwait(false);
        }

        static void Pump()
        {
            while (Queue.TryDequeue(out var action))
                action();
        }
    }
}
