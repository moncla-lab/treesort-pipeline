# Start from the official, minimal Micromamba image.
# Docker will automatically select the arm64 or amd64 variant.
FROM mambaorg/micromamba:latest

# Copy your Bioconda environment definition into the container.
COPY env.yml /tmp/env.yml

# Configure Bioconda
RUN micromamba config append channels conda-forge && \ 
  micromamba config append channels bioconda && \
  micromamba config set channel_priority strict

# Create the Conda environment from your file.
# The 'micromamba clean' step helps keep the final image size down.
RUN micromamba install -y -n base -f /tmp/env.yml && \
  micromamba clean --all --yes

# 
COPY entrypoint-aws-batch /sbin
USER root
RUN chmod a+rx /sbin/entrypoint*

# This is the command that will run when the container starts.
# It ensures that your pipeline command executes inside your new Conda environment.
# For example, to run Snakemake: # The fixed part: This activates the 'base' environment and waits for a command. # ... (your FROM, COPY, and RUN lines) ... # Use the "shell form" of ENTRYPOINT to explicitly run our command # inside the activated Conda environment. The "$@" passes along any # arguments from the docker run command. # The fixed part: activate the 'base' env and prepare to run a command
ENTRYPOINT ["micromamba", "run", "-n", "base", "/sbin/entrypoint-aws-batch"]
