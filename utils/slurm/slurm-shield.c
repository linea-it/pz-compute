/* slurm-shield - execute program on slurm cluster while protecting slurm from it */

/* Executes and monitors a child process with lower CPU and I/O priority and higher OOM
 * adjustment score relative to the slurm daemon, so that there's a decreased probability
 * of the slurm daemon being killed by the operating system and an increased probability
 * of the child program being killed in a low memory situation. The child process is also
 * monitored and checked for being terminated by signals and then hiding those abnormal
 * terminations from the slurm daemon by returning a simple error result. Similarly, it
 * monitors signals being received by itself, forwarding them to the child and following
 * them with a SIGKILL, as a best effort to terminate a stuck child process.
 *
 * Usage:
 *
 * 	slurm-shield <program> [<args>...]
 *
 * The program is searched using the PATH environment variable.
 */

/* Compile with:
 *
 * 	$ cc -o slurm-shield slurm-shield.c
 */

/* Example usage:
 *
 * 	$ slurm-shield rail-estimate -a fzboost src.pq dest.hdf5
 */

#include <assert.h>
#include <errno.h>
#include <signal.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

#define OOM_ADJUST "/proc/self/oom_score_adj"

// From linux/ioprio.h
#define IOPRIO_CLASS_SHIFT      13
#define IOPRIO_CLASS_MASK       0x07
#define IOPRIO_PRIO_MASK        ((1UL << IOPRIO_CLASS_SHIFT) - 1)

#define IOPRIO_PRIO_CLASS(ioprio)       \
        (((ioprio) >> IOPRIO_CLASS_SHIFT) & IOPRIO_CLASS_MASK)
#define IOPRIO_PRIO_DATA(ioprio)        ((ioprio) & IOPRIO_PRIO_MASK)
#define IOPRIO_PRIO_VALUE(class, data)  \
        ((((class) & IOPRIO_CLASS_MASK) << IOPRIO_CLASS_SHIFT) | \
         ((data) & IOPRIO_PRIO_MASK))

#define IOPRIO_CLASS_BE 2
#define IOPRIO_WHO_PROCESS 1

volatile sig_atomic_t signal_number;

void on_signal(int signo)
{
	signal_number = signo;
}

void oom_nice(int inc)
{
	FILE *fp;
	int adj;

	fp = fopen(OOM_ADJUST, "r");
	if (fp != NULL) {
		fscanf(fp, "%d", &adj);
		fclose(fp);
		fp = fopen(OOM_ADJUST, "w");
		if (fp != NULL) {
			adj += inc;
			if (adj > 1000)
				adj = 1000;

			fprintf(fp, "%d", adj);
			fclose(fp);
		}
	}
}

void ioprio(int prio)
{
	int mask;

	mask = IOPRIO_PRIO_VALUE(IOPRIO_CLASS_BE, prio);
	syscall(SYS_ioprio_set, IOPRIO_WHO_PROCESS, 0, mask);
}

void child(char *argv[])
{
	oom_nice(900);
	nice(1);
	ioprio(7);
	execvp(argv[1], &argv[1]);
}

int main(int argc, char *argv[])
{
	int child_status;
	pid_t child_pid, r;

	struct sigaction action;
	sigset_t blockall, blocknone, oldmask;

	if (argc < 2)
		return EXIT_FAILURE;

	sigfillset(&blockall);
	sigemptyset(&blocknone);

	action = (struct sigaction) {
		.sa_handler = on_signal,
		.sa_mask = blockall,
		.sa_flags = SA_RESETHAND,
	};

	// Initially block all signals.
	sigprocmask(SIG_SETMASK, &blockall, &oldmask);

	child_pid = fork();

	if (!child_pid) {
		// Child process here. Restore signal mask and then execute child.
		sigprocmask(SIG_SETMASK, &oldmask, NULL);
		child(argv);
		abort();
	}

	// Parent process here.
	// Listen to the SIGINT, SIGTERM, SIGQUIT and SIGHUP signals.
	sigaction(SIGINT, &action, NULL);
	sigaction(SIGTERM, &action, NULL);
	sigaction(SIGQUIT, &action, NULL);
	sigaction(SIGHUP, &action, NULL);

	// Unblock all signals here.
	sigprocmask(SIG_SETMASK, &blocknone, NULL);

	if (!signal_number) {
		// Wait for child.
		r = wait(&child_status);
	}
	else {
		// If already received an early signal, simulate an interrupt to enter the
		// error handler.
		errno = EINTR;
		r = -1;
	}

	if (r < 0) {
		// Signal received, send SIGTERM, then SIGKILL to the child.
		assert(errno == EINTR);
		psignal(signal_number, "slurm-shield: Signal received");
		fprintf(stderr, "slurm-shield: Terminating child...\n");
		kill(child_pid, SIGTERM);
		sleep(1);
		fprintf(stderr, "slurm-shield: Calling kill(SIGKILL)...\n");
		fflush(stderr);
		kill(child_pid, SIGKILL);
		fprintf(stderr, "slurm-shield: Finished kill(SIGKILL).\n");
		fflush(stderr);
		fprintf(stderr, "slurm-shield: Calling waitpid(WNOHANG)...\n");
		fflush(stderr);
		r = waitpid(child_pid, &child_status, WNOHANG);
		fprintf(stderr, "slurm-shield: Finished waitpid(WNOHANG)...\n");
		fflush(stderr);
	}

	if (r > 0) {
		if (WIFEXITED(child_status))
			return WEXITSTATUS(child_status);

		psignal(WTERMSIG(child_status), "slurm-shield: Child returned signal");
	}

	fprintf(stderr, "slurm-shield: Returning failure.\n");
	fflush(stderr);

	return EXIT_FAILURE;
}
