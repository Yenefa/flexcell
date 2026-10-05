#include <execinfo.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <unistd.h>

static int trace_fd = STDERR_FILENO;

static void capture_abort(int signal_number) {
    void *frames[96];
    const char label[] = "\nQ8_DIAGNOSTIC_SIGABRT_NATIVE_STACK\n";
    write(STDERR_FILENO, label, sizeof(label) - 1);
    int count = backtrace(frames, 96);
    backtrace_symbols_fd(frames, count, trace_fd);
    signal(signal_number, SIG_DFL);
    raise(signal_number);
}

__attribute__((constructor)) static void install_handler(void) {
    char path[160];
    snprintf(path, sizeof(path), "/tmp/q8_native_20261005/backtrace_%d.log", getpid());
    int descriptor = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (descriptor >= 0) trace_fd = descriptor;
    signal(SIGABRT, capture_abort);
}
