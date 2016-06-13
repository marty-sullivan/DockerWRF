FROM centos
MAINTAINER Marty Sullivan <marty.sullivan@cornell.edu>

ENV PATH      $PATH:/usr/lib64/mpich/bin
ENV CC 		    gcc
ENV CXX 	    g++
ENV FC 		    gfortran
ENV FCFLAGS 	-m64
ENV F77		    gfortran
ENV FFLAGS	  -m64
ENV NETCDF	  /usr
ENV WRFIO_NCD_LARGE_FILE_SUPPORT 1

COPY    ssh /root/.ssh
WORKDIR /opt
COPY    *.tar.gz ./

RUN yum install -y epel-release && \
    yum install -y \
      openssh-server \
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
    ssh-keygen -A && \
    ls ./*.tar.gz | xargs -n1 tar -xf && \
    rm -f *.tar.gz

# Build WRF
WORKDIR  ./WRFV3
RUN      ./compile em_real >& log.compile

# Build WPS
WORKDIR  ../WPS
RUN      ./compile >& log.compile

WORKDIR /root
EXPOSE  22
CMD     ["/usr/sbin/sshd", "-D"]
