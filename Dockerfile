FROM centos
MAINTAINER Marty Sullivan <marty.sullivan@cornell.edu>

# Compile Environment
ENV PATH      $PATH:/usr/lib64/mpich/bin
ENV CC        gcc
ENV CXX       g++
ENV FC        gfortran
ENV FCFLAGS   -m64
ENV F77		    gfortran
ENV FFLAGS	  -m64
ENV NETCDF	  /usr

WORKDIR /opt
COPY    *.tar.gz ./

RUN yum install -y epel-release && \
    yum install -y \
      wget \ 
      m4 \
      make \
      tcsh \
      which \
      time \
      gcc \
      gcc-c++ \
      gcc-gfortran \
      netcdf-devel \
      netcdf-cxx-devel \
      netcdf-fortran-devel \
      netcdf-mpich-devel \
      netcdf-fortran-mpich-devel \
      mpich-devel \
      libpng-devel \
      zlib-devel \
      jasper-devel && \
    yum clean all && \
    ls ./*.tar.gz | xargs -n1 tar -xf && \
    rm -f *.tar.gz

# Build WRF
WORKDIR  ./WRFV3
RUN      ./compile em_real >& log.compile

# Build WPS
WORKDIR  ../WPS
RUN      ./compile >& log.compile

# Default Run Environment
ENV INPUT_DATA  "GFS"
ENV INPUT_RES   "1p0"
ENV LATITUDE    "42.4534"
ENV LONGITUDE   "76.4735"
ENV POINTS_WE   "94"
ENV POINTS_SN   "38"
ENV XSPACING    "32000"
ENV YSPACING    "32000"

WORKDIR /root
COPY    scripts/* ./

CMD ["/root/entry.py"]
