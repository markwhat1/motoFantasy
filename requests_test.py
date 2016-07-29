from selenium import webdriver
from bs4 import BeautifulSoup
import pp
import pandas as pd

browser = webdriver.Firefox()
baseUrl = 'https://www.motocrossfantasy.com/'


def mf_auth():
    browser.get('https://motocrossfantasy.com')
    emailElem = browser.find_element_by_name('login_username')
    emailElem.send_keys('markwhat')
    passwordElem = browser.find_element_by_name('login_password')
    passwordElem.send_keys('yamaha')
    # hiddenElem = browser.find_element_by_name('login')
    # hiddenElem = send_keys('true')
    submitElem = browser.find_element_by_class_name('submit')
    submitElem.click()
    return


def mf_riderLists(value):
    if value == int(450):
        # 450 class url
        rider_url = baseUrl + 'user/pick-riders/2016-MX/3525/373'
    elif value == int(250):
        # 250 class url
        rider_url = baseUrl + 'user/pick-riders/2016-MX/3525/374'
    else:
        pp('Error getting class URL!')

    browser.get(rider_url)
    html = browser.page_source
    soup = BeautifulSoup(html, markup='html')
    table = soup.find("table", attrs={"class": "pickriders_table"})
    df = pd.read_html(table)
    df

    # raw_df = pd.DataFrame(raw_data, columns = ['name', 'handicap', 'last_finish', 'underdog'])
    # for row in table:
    # pp(table)
    return

mf_auth()
mf_riderLists(450)
