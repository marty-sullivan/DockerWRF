FROM centos

MAINTAINER Marty Sullivan <marty.sullivan@cornell.edu>

WORKDIR /usr/local
COPY *.tar.gz ./

ENV PATH $PATH:/usr/lib64/mpich/bin
ENV CC 		gcc
ENV CXX 	g++
ENV FC 		gfortran
ENV FCFLAGS 	-m64
ENV F77		gfortran
ENV FFLAGS	-m64
ENV NETCDF	/usr
ENV WRFIO_NCD_LARGE_FILE_SUPPORT 1

RUN 	yum install -y epel-release && \
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
	sed -i 's/PermitRootLogin without-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
	echo 'root:root' | chpasswd && \
	ssh-keygen -A && \
	ls ./*.tar.gz | xargs -n1 tar -xf && \
	rm -f *.tar.gz

# Build WRF
WORKDIR ./WRFV3
COPY configure.wrf ./
RUN ./compile em_real >& log.compile

# Build WPS
WORKDIR ../WPS
COPY configure.wps ./
RUN ./compile >& log.compile

EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]
