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
        static readonly SynchronizationContext MainContext;

        static MainThreadDispatcher()
        {
            MainThreadId = Thread.CurrentThread.ManagedThreadId;
            MainContext = SynchronizationContext.Current;
            EditorApplication.update += Pump; // fallback when no context was captured
        }

        public static bool IsMainThread => Thread.CurrentThread.ManagedThreadId == MainThreadId;

        public static bool HasMainThreadContext => MainContext != null;

        /// <summary>
        /// Run action on the main thread soon. Unlike EditorApplication.delayCall (which is not drained
        /// while Unity is in the background), this posts to the main SynchronizationContext and wakes
        /// the editor loop, so it also runs promptly when another app has focus.
        /// </summary>
        public static void Defer(Action action)
        {
            Queue.Enqueue(action);
            Wake();
        }

        static void Wake()
        {
            MainContext?.Post(_ =>
            {
                Pump();
                EditorApplication.QueuePlayerLoopUpdate();
            }, null);
        }

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
            Wake();
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
