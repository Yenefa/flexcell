"""Bounded image encoding outside ROS callbacks; overflow is a collection error."""
import json
from queue import Empty, Full, Queue
import threading


class FrameWriter:
    def __init__(self, out, encode, max_pending=64):
        self.out, self.encode = out, encode
        self.queue = Queue(maxsize=max_pending)
        self.errors, self.rejected = [], []
        self.written = self.valid = self.high_watermark = 0
        self.stopping = threading.Event()
        self.drained = False
        # Open synchronously so an unwritable destination fails before collection.
        self.stream = (out / 'frames.jsonl').open('x')
        self.worker = threading.Thread(target=self._run, name='rgb-encoder', daemon=True)
        self.worker.start()

    def submit(self, row, message):
        if self.stopping.is_set() or not self.worker.is_alive():
            reason = 'image_writer_not_running'
        else:
            try:
                self.queue.put_nowait((row, message))
                self.high_watermark = max(self.high_watermark, self.queue.qsize())
                return True
            except Full:
                reason = 'image_writer_queue_full'
        row['valid'] = False
        row['reasons'].append(reason)
        self.rejected.append(row)
        self.errors.append('%s: frame %d' % (reason, row['frame_index']))
        return False

    def _run(self):
        try:
            while not self.stopping.is_set() or not self.queue.empty():
                try:
                    row, message = self.queue.get(timeout=.05)
                except Empty:
                    continue
                try:
                    self.encode(self.out / row['image'], message)
                except Exception as exc:  # Report I/O/encoding failure; never fabricate an image.
                    reason = 'image_write_failed: ' + str(exc)
                    row['reasons'].append(reason)
                    self.errors.append(reason)
                row['valid'] = not row['reasons']
                self.stream.write(json.dumps(row, allow_nan=False) + '\n')
                self.stream.flush()
                self.written += 1
                self.valid += int(row['valid'])
                self.queue.task_done()
        except Exception as exc:
            self.errors.append('frame_manifest_write_failed: ' + str(exc))
        finally:
            self.stream.close()

    def close(self, timeout=10):
        self.stopping.set()
        self.worker.join(timeout)
        self.drained = not self.worker.is_alive() and self.queue.empty()
        if not self.drained:
            self.errors.append('image_writer_drain_incomplete')
        return self.drained and not self.errors

    def report(self):
        return dict(frames_written=self.written, valid_frames=self.valid,
                    queue_capacity=self.queue.maxsize, queue_high_watermark=self.high_watermark,
                    drain_completed=self.drained, errors=list(self.errors),
                    rejected_frames=list(self.rejected))
