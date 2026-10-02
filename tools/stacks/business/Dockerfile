FROM frappe/bench:latest
# Switch to root to install packages
USER root
# Install supervisor
RUN apt update && apt install -y supervisor
# Create log directory to avoid permission issues
RUN mkdir -p /var/log/supervisor && chmod -R 777 /var/log/supervisor
# Copy custom supervisord config into container
COPY supervisord.conf /etc/supervisord.conf
# Switch to frappe user to install Python 3.14.2 via pyenv (matches staging / prod v16 runtime)
USER frappe
RUN cd $(pyenv root)/plugins/python-build && git pull && pyenv install -s 3.14.2
RUN bash -lc "source /home/frappe/.nvm/nvm.sh && nvm install 24.13.0 && nvm alias default 24.13.0"
# Download NLTK/textblob corpora needed by Helpdesk article search
# (frappe user's HOME is not volume-mounted, so this persists across container rebuilds)
RUN pip install --no-cache-dir --user textblob nltk \
    && python3 -m textblob.download_corpora \
    && python3 -c "import nltk; nltk.download('punkt_tab'); nltk.download('averaged_perceptron_tagger_eng')"
# Default command
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
