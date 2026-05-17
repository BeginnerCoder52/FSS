#include <iostream>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/videodev2.h>
#include <cstring>
#include <errno.h>

#include "../include/UvcStillMagic.hpp"

int main()
{
    const char *device = "/dev/video0";
    int fd = open(device, O_RDWR);

    if (fd == -1)
    {
        std::cerr << "Error opening " << device << ": " << strerror(errno) << std::endl;
        return 1;
    }

    std::cout << "Successfully opened " << device << std::endl;

    struct v4l2_capability cap;
    if (ioctl(fd, VIDIOC_QUERYCAP, &cap) == -1)
    {
        std::cerr << "Error querying capabilities: " << strerror(errno) << std::endl;
        close(fd);
        return 1;
    }

    std::cout << "Driver: " << cap.driver << std::endl;
    std::cout << "Card: " << cap.card << std::endl;
    std::cout << "Bus info: " << cap.bus_info << std::endl;
    std::cout << "Version: " << ((cap.version >> 16) & 0xFF) << "."
              << ((cap.version >> 8) & 0xFF) << "."
              << (cap.version & 0xFF) << std::endl;

    if (cap.capabilities & V4L2_CAP_VIDEO_CAPTURE)
    {
        std::cout << "Device supports video capture." << std::endl;
    }
    if (cap.capabilities & V4L2_CAP_STREAMING)
    {
        std::cout << "Device supports streaming I/O." << std::endl;
    }

    // Check for still image support using the magic number if possible
    // This is just a test to see if we can use the magic number in a request
    struct v4l2_format fmt;
    std::memset(&fmt, 0, sizeof(fmt));
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;

    if (ioctl(fd, VIDIOC_G_FMT, &fmt) == -1)
    {
        std::cerr << "Error getting current format: " << strerror(errno) << std::endl;
    }
    else
    {
        std::cout << "Current Resolution: " << fmt.fmt.pix.width << "x" << fmt.fmt.pix.height << std::endl;
    }

    close(fd);
    std::cout << "Device closed." << std::endl;

    return 0;
}
