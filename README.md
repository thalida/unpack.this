# unpack.link

## Starting Services

Use `export UNPACK_HOST=10.0.12.195 && docker-compose up --build`
'UNPACK_DEBUG`
Check that it's running with `docker ps`


## Examples
### Twitter
```
thread_example = 1048986902098059267
quoted_example = 1048977169186271232
multi_quote_example = 1048991778119008258
simple_weird_tree = 1048989029486809088
medium_weird_tree = 1049037454710394881
large_weird_tree = 946823401217380358
deleted_quoted_tweet = 946795191784132610
```

# TODOs

## 8 June
- [x] Set general staleness checks (type has a default, rules can override)
- [ ] Start rendering nodes.
    - [x] Setup vue.
    - [x] Setup typescript
    - [ ] Create new index view
        - [x] Form enter a url, get redirected to results view
        - [ ] Use custom validation messages/display
    - [ ] Create new results view
        - [x] has url field (silent refreshing(?))
        - [ ] has query controls
        - [x] hit api endpoints
        - [x] socketio setup
        - [x] render node on socket push
        - [ ] setup proper storage
    - [ ] Results
        - [x] Render each link in it's level
        - [ ] Organize Level
            - [ ] not from same domain, then same domain
            - [ ] order both by order found on page
        - [ ] Add checkbox to show the links available with that link
    - [ ] Site Data
        - [ ] fetch site data for node on quick view load
    - [ ] Update python functions to use proper/better named param style
- [x] Move upnack folder to top level
- [ ] Cache db queries
- [ ] Don't fetch css or fonts
- [ ] Don't store site contents
- [ ] Store link index on page
- [ ] Add better comments and documentation
    - [x] Figure out one of those self documenting sites (sphinx)
    - [ ] Vue/JS autodocs(?)
- [x] split out important shit from __init__ it's okay for readability!!!
- [x] change any print statements to log.info things
- [x] move broadcaster to be under queue manager
- [ ] figure out why queues aren't being deleted

## Some Date
- flask app
- pass url to unpack.py api call
- setup json format for data
- return json


request url or id

if id exists
    check if the data is ready
    if ready
        show it
    else
        fire api call to get data
        show input to get notified/text to bookmark
else
    show error

if url
    id = get id for url
    redirect to id

pk_id <==> path
pk_id, date, path, meta
pk_id, pk_id, relationship (quote, reply, link)
