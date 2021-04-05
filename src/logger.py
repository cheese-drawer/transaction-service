import asyncio
import logging
import threading
from typing import Optional, Callable

from amqp_worker.connection import Channel, ConnectionParameters
from amqp_worker.queue_worker import QueueProducer, JSONGzipMaster

from .mode import get_mode


MODE = get_mode()
logger = logging.getLogger(__name__)


class AMQPLogHandler(logging.Handler):
    """Send logs over AMQP via given producer."""

    queue: str
    producer: QueueProducer

    def __init__(self, queue: str, producer: QueueProducer) -> None:
        self.queue = queue
        self.producer = producer
        super().__init__()

    def emit(self, record: logging.LogRecord) -> None:
        """Send log record as message to logging queue."""
        logger.debug(f'AMQPLogHandler emitting record: {record}')

        # aio_pika (library under the hood in amqp_worker) doesn't expose any
        # synchronous versions of it's `create_task` methods, requiring
        # QueueProducer.publish to be asynchronous. This means `publish` must
        # be awaited here, but we want our LogHandler to be synchronous so that
        # we don't have to change our logging API usage anywhere else. AFAIK
        # there's two ways around this, either:
        # A) wrap the call to `publish` in an `asyncio.run()` call, which can't
        # be done in the main thread since the entire program is already in an
        # asyncio event loop on the main thread (this means spawn a new thread
        # just to call `publish`), or
        # B) use a different library entirely (pika) to run the publishing of
        # LogRecords over AMQP.
        #
        # For now, I'm going with option A.
        def thread_fn(queue: str, record: logging.LogRecord) -> None:
            async def pub() -> None:
                return await self.producer.publish(queue, record)

            asyncio.run(pub())

        thread = threading.Thread(target=thread_fn, args=(self.queue, record,))
        thread.start()


def _determine_log_level() -> int:
    if MODE == 'development':
        return logging.INFO

    if MODE == 'debug':
        return logging.DEBUG

    return logging.ERROR


def setup_logger_service(
    connection_params: ConnectionParameters,
    pattern_factory: Optional[Callable[[Channel], JSONGzipMaster]] = None
) -> QueueProducer:
    """
    Configure logger to send records over AMQP.

    Sends logs by level to logging.<level> (error, warn, info, or debug)
    using amqp_worker.QueueProducer.
    """
    if pattern_factory:
        producer = QueueProducer(
            connection_params,
            name='LogProducer',
            pattern_factory=pattern_factory)
    else:
        producer = QueueProducer(
            connection_params,
            name='LogProducer')

    # err_handler = AMQPLogHandler('logging.error', producer)
    # err_handler.setLevel(logging.ERROR)
    # warn_handler = AMQPLogHandler('logging.warn', producer)
    # warn_handler.setLevel(logging.WARNING)
    # info_handler = AMQPLogHandler('logging.info', producer)
    # info_handler.setLevel(logging.INFO)
    debug_handler = AMQPLogHandler('logging', producer)
    debug_handler.setLevel(logging.DEBUG)

    logging.basicConfig(
        handlers=[debug_handler],
        level=_determine_log_level(),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    return producer
