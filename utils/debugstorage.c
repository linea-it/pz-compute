/* debugstorage - Simple I/O read/write benchmarks */

/* Run a read or write test, possibly multiple times and output the time of each
 * operation. When writing, random data is generated.
 *
 * Usage:
 *   debugstorage [-r|-w] [-s <size>] [-l <loop>] [<fileprefix>]
 *
 * Options:
 *  <fileprefix>	Text used when creating file names [default: "random"].
 *  -r			Read existing files.
 *  -w			Write new files [default].
 *  -s <size>		Set the file size [default: 134217728].
 *  -l <loop>		Repeat the I/O operation [default: 5].
 *
 * File names will have the format: "<fileprefix>-<loopiter>.out".
 * All files will have the same random content.
 * All memory allocated for the requested size will be locked.
 */

/* Compile with:
 *
 * 	$ cc -o debugstorage debugstorage.c
 */

/* Example usage:
 *
 * 	$ debugstorage -w -s 65536 -l 10 testfiles
 * 	$ debugstorage -r -s 65536 -l 10 testfiles
 */

#define _GNU_SOURCE
#include <assert.h>
#include <fcntl.h>
#include <getopt.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define FILE_SIZE (1<<27)
#define LOOP 5
#define FNAME "random"

static const char OPEN[] = "open";
static const char CLOSE[] = "close";
static const char READ[] = "read";
static const char WRITE[] = "write";

enum event {
	begin,
	end,
};

enum iodir {
	iodir_read,
	iodir_write,
};

struct OpEvent {
	const char *op;
	enum event event;
	struct timespec time;
};

struct OpEventArray {
	struct OpEvent *op_events;
	size_t len;
};

struct Configuration {
	enum iodir iodir;
	size_t file_size;
	unsigned loop;
	const char *fname;
};

void *alloc_random_data(size_t n, enum iodir iodir)
{
	void *data;
	int r, fd;

	// Allocate aligned memory to ensure fast memory access.
	data = mmap((void *)0x10000000, n, PROT_READ|PROT_WRITE,
		    MAP_ANONYMOUS|MAP_PRIVATE|MAP_NORESERVE, -1, 0);
	assert(data != NULL);

	// Use huge pages to ensure fast TLB access.
	r = madvise(data, n, MADV_HUGEPAGE);
	assert(r == 0);

	if (iodir == iodir_write) {
		fd = open("/dev/urandom", O_RDONLY);
		assert(fd >= 0);
		read(fd, data, n);
		close(fd);
		mprotect(data, n, PROT_READ);
	}

	// Disable swapping.
	mlock(data, n);

	return data;
}

void free_random_data(void *data, size_t n)
{
	munmap(data, n);
}

// Add a new event entry in the event array.
void op_event_append(struct OpEventArray *array, const char *op, enum event ev)
{
	void *tmp;

	struct timespec t;

	clock_gettime(CLOCK_MONOTONIC, &t);

	tmp = realloc(array->op_events, (array->len + 1) * sizeof(struct OpEvent));
	assert(tmp != NULL);

	array->op_events = tmp;
	array->op_events[array->len] = (struct OpEvent) { op, ev, t };
	array->len++;
}

double timediff(const struct timespec *end, const struct timespec *begin)
{
	time_t sec;
	long nsec;

	sec = end->tv_sec - begin->tv_sec;
	nsec = end->tv_nsec - begin->tv_nsec;

	return (double)sec + (double)nsec/1e9;
}

void op_event_dump(const struct OpEventArray *array)
{
	size_t i;
	double d;

	struct OpEvent *b, *e;

	for (i = 0; i < array->len; i += 2) {
		b = &array->op_events[i];
		e= &array->op_events[i+1];
		d = timediff(&e->time, &b->time);

		assert(b->event == begin);
		assert(e->event == end);

		printf("%s %0.3f\n", b->op, d);
	}
}

void op_event_free(struct OpEventArray *array)
{
	free(array->op_events);
	array->len = 0;
}

void do_io(const char *fname, void *data, size_t n, enum iodir iodir,
	   struct OpEventArray *array)
{
	const char *op;
	int fd, flags;
	ssize_t ss;
	ssize_t (*io)(int, void *, size_t);

	if (iodir == iodir_read) {
		flags = O_RDONLY;
		op = READ;
		io = read;
	}
	else {
		flags = O_WRONLY | O_CREAT | O_TRUNC;
		op = WRITE;
		io = (ssize_t (*)(int, void *, size_t))write;
	}

	op_event_append(array, OPEN, begin);
	fd = open(fname, flags, 0666);
	if (fd < 0) {
		perror("open()");
		exit(EXIT_FAILURE);
	}
	op_event_append(array, OPEN, end);

	op_event_append(array, op, begin);
	ss = io(fd, data, n);
	if (ss < 0) {
		perror("io()");
		abort();
	}
	assert((size_t)ss == n);
	op_event_append(array, op, end);

	op_event_append(array, CLOSE, begin);
	close(fd);
	op_event_append(array, CLOSE, end);
}

void parse_cmdline(int argc, char *argv[], struct Configuration *cfg)
{
	int ch;
	unsigned long long val;

	static const struct option longopts[] = {
		{ "read", no_argument, NULL, 'r' },
		{ "write", no_argument, NULL, 'w' },
		{ "size", required_argument, NULL, 's' },
		{ "loop", required_argument, NULL, 'l' },
		{ 0 }
	};

	// Set defaults.
	cfg->iodir = iodir_write;
	cfg->file_size = FILE_SIZE;
	cfg->loop = LOOP;
	cfg->fname = FNAME;

	while (true) {
		ch = getopt_long(argc, argv, "rws:l:", longopts, NULL);

		if (ch < 0) break;

		switch (ch) {
		case 'r':
			cfg->iodir = iodir_read;
			break;
		case 'w':
			cfg->iodir = iodir_write;
			break;
		case 's':
			val = strtoull(optarg, NULL, 0);
			cfg->file_size = val;
			break;
		case 'l':
			val = strtoull(optarg, NULL, 0);
			cfg->loop = val;
			break;
		default:
			fprintf(stderr, "Usage: %s [-r|-w] [-s <size>] [-l <loop>] "
				        "[<fileprefix>]\n", argv[0]);
			exit(EXIT_FAILURE);
		}
	}

	if (optind < argc)
		cfg->fname = argv[optind];
}

int main(int argc, char *argv[])
{
	void *data;
	char buff[PATH_MAX];
	unsigned i;

	struct Configuration cfg;
	struct OpEventArray op_events = { 0 };

	parse_cmdline(argc, argv, &cfg);

	data = alloc_random_data(cfg.file_size, cfg.iodir);

	for (i = 0; i < cfg.loop; i++) {
		snprintf(buff, PATH_MAX, "%s-%u.out", cfg.fname, i);
		do_io(buff, data, cfg.file_size, cfg.iodir, &op_events);
	}

	op_event_dump(&op_events);
	op_event_free(&op_events);
	free_random_data(data, cfg.file_size);

	return 0;
}
