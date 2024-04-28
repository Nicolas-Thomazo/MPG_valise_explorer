FROM python:3.10

COPY /scrap /scrap
COPY /config /config
COPY /utils /utils
COPY /sql /sql
COPY requirements.txt .
COPY scrap_league.py .
COPY get_matchweeks_not_scrapped.py .
COPY get_all_bonus.py .

#We have to create the folder to be able to write exports files
RUN mkdir -p /exports

RUN pip install --trusted-host pypi.python.org -r requirements.txt

RUN apt-get update && apt-get install -y wget unzip && \
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb && \
    apt-get clean

# CMD ["python", "get_all_bonus.py"]