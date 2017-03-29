import sys
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy import create_engine
from sqlalchemy import desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound

BASE_URL = 'https://www.indiegala.com'

Base = declarative_base()


class History(Base):
    __tablename__ = 'history'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    url = Column(String)
    is_happy_hour = Column(Boolean)
    created_at = Column(DateTime, default=datetime.now())

    def __repr__(self):
        return "<History(name='%s', url='%s', is_happy_hour='%s', created_at='%s')>" % (
            self.name, self.url, self.is_happy_hour, self.created_at
        )

    def __str__(self):
        return "%s: %s" % (self.name, self.url)


def http_get(url: str) -> str:
    driver = webdriver.PhantomJS()
    driver.get(url)
    src = driver.page_source
    driver.quit()

    return src


def extract_title(elem) -> str:
    a = elem.find('div', class_='mega-menu-item-title').find('a')
    return a.string


def extract_url(elem) -> str:
    a = elem.find('div', class_='mega-menu-item-title').find('a')
    return urljoin(BASE_URL, a['href'])


def is_happy_hour(elem) -> bool:
    try:
        img = elem.find('div', class_='extra-info-cont').find('img')
        return img['alt'].lower() == 'happy hour'
    except AttributeError:
        return False


def parse_index(html: str) -> list:
    root = BeautifulSoup(html, 'lxml')
    return [
        History(name=extract_title(li), url=extract_url(li), is_happy_hour=is_happy_hour(li))
        for li in root.find_all('li', class_='mega-menu-item relative')
    ]


def is_new_happy_hour(session, history: History) -> bool:
    if not history.is_happy_hour:
        return False

    try:
        past_sale = session.query(History) \
            .filter_by(name=history.name, url=history.url) \
            .order_by(desc(History.created_at)) \
            .limit(1) \
            .one()
        return not past_sale.is_happy_hour
    except NoResultFound:
        return True


def main():
    engine = create_engine('sqlite:///ig-hh.db')
    Base.metadata.create_all(bind=engine)

    current_sale = parse_index(http_get(BASE_URL))
    print(f'Total: {len(current_sale)}', file=sys.stderr)

    session = sessionmaker(bind=engine)()

    new_happy_hour = list(filter(lambda s: is_new_happy_hour(session, s), current_sale))
    print(f'New HH bundle: {len(new_happy_hour)}', file=sys.stderr)

    session.add_all(current_sale)
    session.commit()

    # example) Discord webhooks
    DISCORD_WEBHOOK_URL = 'https://discordapp.com/api/webhooks/foo/bar'
    requests.post(DISCORD_WEBHOOK_URL, json={
        'content': 'Happy hour started!\n' + '\n'.join([str(x) for x in new_happy_hour])
    })


if __name__ == '__main__':
    main()
