clean:
	rm -fr build/
	rm -f .coverage
	rm -f src/*.pyc
	rm -fr src/__pycache__/

all:
	echo "TODO"

test:
	(cd $(TESTBASE); \
	echo $(wildcard $(CURDIR)/src/*_test.py) | xargs -n 1 coverage run -p)

install:
	python setup.py install --root $(DESTDIR) $(COMPILE)
	mkdir -p $(DESTDIR)/opt/snmpcollector/src/
	cp src/*.py $(DESTDIR)/opt/snmpcollector/src/
	ln -sf /opt/snmpcollector/src/trigger.py \
		$(DESTDIR)/opt/snmpcollector/snmpcollector-trigger
	ln -sf /opt/snmpcollector/src/snmptest.py \
		$(DESTDIR)/opt/snmpcollector/snmpcollector-test
	mkdir -p $(DESTDIR)/etc/default $(DESTDIR)/etc/init.d
	install -D -m600 etc/snmpcollector.yaml $(DESTDIR)/etc/
	install -D etc/snmpcollector.default $(DESTDIR)/etc/default/snmpcollector
	install -D snmpcollector.init $(DESTDIR)/etc/init.d/snmpcollector
