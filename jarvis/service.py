"""Reusable threaded orchestration boundary for desktop and CLI front ends."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Event, Lock, Thread, current_thread
from typing import Any, Callable

from jarvis.app import AssistantState, run_assistant


class AssistantEventKind(str, Enum):
    STATE = "state"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass(frozen=True)
class AssistantEvent:
    """Content-free event published to a presentation layer."""

    kind: AssistantEventKind
    state: AssistantState | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if self.kind == AssistantEventKind.STATE and self.state is None:
            raise ValueError("state events require a state")
        if self.kind != AssistantEventKind.STATE and self.state is not None:
            raise ValueError("only state events may include a state")
        if "\n" in self.detail or len(self.detail) > 160:
            raise ValueError("event detail must be a short single line")


class AssistantService:
    """Run the injected assistant executor on a stoppable worker thread.

    The service owns no backend resources itself; the executor remains
    responsible for constructing and releasing them. Event callbacks run on
    the worker thread and must be quick. Front ends should queue them onto
    their own event loop.
    """

    def __init__(self, *runner_args: Any, runner: Callable[..., Any] = run_assistant,
                 event_sink: Callable[[AssistantEvent], None] | None = None,
                 **runner_kwargs: Any) -> None:
        self._runner_args = runner_args
        self._runner_kwargs = dict(runner_kwargs)
        self._runner = runner
        self._event_sink = event_sink
        self._stop = Event()
        self._lock = Lock()
        self._thread: Thread | None = None
        self._failure: BaseException | None = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    @property
    def failure(self) -> BaseException | None:
        with self._lock:
            return self._failure

    def start(self) -> None:
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("assistant service has already been started")
            self._thread = Thread(target=self._run, name="jarvis-assistant", daemon=True)
            self._thread.start()

    def request_stop(self) -> None:
        """Ask the runner to stop between audio reads and response stages."""
        self._stop.set()

    def wait(self, timeout: float | None = None) -> bool:
        with self._lock:
            thread = self._thread
        if thread is None:
            return True
        if thread is current_thread():
            raise RuntimeError("assistant service cannot wait from its worker")
        thread.join(timeout)
        return not thread.is_alive()

    def _publish(self, event: AssistantEvent) -> None:
        if self._event_sink is not None:
            self._event_sink(event)

    def _run(self) -> None:
        try:
            kwargs = dict(self._runner_kwargs)
            kwargs["on_state"] = lambda state: self._publish(
                AssistantEvent(AssistantEventKind.STATE, state=state))
            kwargs["stop_requested"] = self._stop.is_set
            kwargs["report"] = kwargs.get("report", lambda _message: None)
            self._runner(*self._runner_args, **kwargs)
        except BaseException:
            with self._lock:
                self._failure = RuntimeError("assistant service stopped because a local component failed")
            self._publish(AssistantEvent(AssistantEventKind.ERROR,
                                         detail="A local component failed"))
        finally:
            self._publish(AssistantEvent(AssistantEventKind.STOPPED))
