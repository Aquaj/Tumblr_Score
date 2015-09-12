import requests
from BeautifulSoup import BeautifulSoup
import pickle
import networkx
from multiprocessing import Process, Lock, Queue, Value
from multiprocessing.queues import SimpleQueue
import sys, time
import operator

ANALYSIS = True
REGENERATE = True
LOGGING = True
VISUALIZATION = True
EVALUATE_CENTRALITY = True
SourceURL = "http://breadstyx.tumblr.com/notes/128187440953/rvY4jeyS6"

dumpfile = "score_dump"

def scrapping(FetchUrl, q, l):
	url = ""
	notes=[]
	reblogs = 0
	noteCount = 0

	print "\n Scrapping pages to get the notes.  -- Fuck The API"
	while(True):
		page = requests.get(FetchUrl+url)
		soup = BeautifulSoup(page.text)
		for l in soup.findAll("li"):
			noteCount += 1
			if(len(l.findAll("a"))>2):
				reblogs+=1
				#print(l.findAll("a")[1].contents[0]+" from "+l.findAll("a")[2].contents[0]+": Added !")
				notes+=[[str(l.findAll("a")[1].contents[0]), str(l.findAll("a")[2].contents[0])]]
		if "original_post" in l['class']:
			print("\r\t\t\t\t\t\t\t\t\r\t\t\r\t"+str(reblogs)+" reblogs added to list !\n")
			print("\r\t\t\t\t\t\t\t\t\r\t\t\r\tNotes composed of "+str(int(reblogs*1.0/(noteCount*1.0)*100))+"% reblogs.\n")
			break
		try:
			urlbis=url
			url="?"+str(soup.findAll("a", attrs={"class":"more_notes_link"})[0].contents[3]).split('GET\',')[1].split(',true')[0][1:-1].split("?")[1]
		except IndexError:
			print "We're not supposed to be here at Aaaaaaall - lalalalilalaaaa"
			break
	
	q.put_nowait(list(set([n[0] for n in notes])))
	q.put_nowait(notes)
	q.put_nowait(noteCount)


def flush():
	print "\r\t\t\t\t\t\t\t\t\r",

def loadingtime(lock, perc=None):
	j = 0
	while True:
		time.sleep(0.5)
		lock.acquire(True)
		flush()
		sys.stdout.write("\r\t\tLoading"+ ("".join(["." for counter in range(j%4)]) if (perc == None) else (" "+str(int(perc.value))+"% " + \
																																			("/" if (j%4 == 0) else \
																																			("-" if (j%4 == 1) else \
																																			("\\" if (j%4 == 2) else \
																																			("|")))))))
		lock.release()
		j+=1

def calcCentrality(G, ret, l, l2):
	l.acquire(True)
	print "\r Detail of calculations: "
	yo = networkx.betweenness_centrality(G)
	l2.acquire(True)
	print "\r\t\t\t\t\t\t\t\t \r\t - Calculation of Betweenness done."
	ret.put_nowait(yo)
	l2.release()
	ya = networkx.closeness_centrality(G)
	l2.acquire(True)
	print "\r\t\t\t\t\t\t\t\t \r\t - Calculation of Closeness done."
	ret.put_nowait(ya)
	l2.release()
	yi = networkx.degree_centrality(G)
	l2.acquire(True)
	print "\r\t\t\t\t\t\t\t\t \r\t - Calculation of Degree done."
	ret.put_nowait(yi)
	l2.release()
	yu = networkx.load_centrality(G)
	l2.acquire(True)
	print "\r\t\t\t\t\t\t\t\t \r\t - Calculation of Load done."
	ret.put_nowait(yu)
	l2.release()
	ret.put('STOP')
	l.release()
	ret.close()
	return

def new_db(src, data, q, l, p):
	db = {}
	l.acquire(True)
	maxlength = len(src)*len(data)
	progress = 0
	for user in src:
		db[user] = []
		for n in sorted(data):
			save = p.value
			if (n[1] == user):
				db[user] += [n[0]]
			progress += 1	
			p.value = progress*1.0/maxlength*100.0
	q.put(db)
	q.close()
	l.release()

if __name__=='__main__':

	global Score, central
	results = Queue()
	lock = Lock()
	lockPrint = Lock()
	dummy = Lock()

	print "\n  --* TUMBLR SCORE - Note Analysis & User Influence v0.5 *--  "

	if(REGENERATE):

		if False:
			p1 = Process(target = loadingtime, args=[lockPrint])
			p1.start()
			p2 = Process(target = scrapping, args=(SourceURL, results, lock))
			p2.start()
			time.sleep(10)
			lock.acquire(True)
			users = results.get()
			notes = results.get()
			noteCount = results.get()
			time.sleep(.1)
			lock.release()
			p1.terminate()

			d = open("debug", 'w')
			pickle.dump([users, notes, noteCount], d)
			d.close()
		else:
			d = open("debug", 'r')
			a = pickle.load(d)
			users = a[0]
			notes = a[1]
			noteCount = a[2]
			d.close()


		if(LOGGING):
			flush()
			print " LOG - Writing a log in readable_note_dump"
			dump = open("readable_note_dump", 'w')
			for n in notes:
				dump.write(" reblogged from : ".join(n)+"\n")

		print " Reformatting data so it can be easily converted to Graph later."

		progress = Value('d', 0.0)
		p1 = Process(target = loadingtime, args=(dummy, progress))
		p1.start()
		p2 = Process(target = new_db, args=(users, notes, results, lock, progress))
		p2.start()
		time.sleep(10)
		lock.acquire(True)
		database = results.get()
		time.sleep(.1)
		lock.release()
		p1.terminate()
		flush()
		print("\tData formatted!")


		if(LOGGING):
			print "\n LOG - Writing a log in readable_db_dump"
			dump = open("readable_db_dump", 'w')
			for user in database.keys():
				if len(database[user])>0:
					dump.write(user + " had their post reblogged by : "+", ".join(database[user])+"\n")
				else:
					dump.write(user + " doesn't have any fRIENDS AND AS SUCH DOESNT HELP PROPAGATE MY POST.\n")


		Score = networkx.MultiDiGraph()
		Score.add_nodes_from(database.iterkeys())
		print " Creating Score Graph using NetworkX."
		for source in database.iterkeys():
			for target in database[source]:
				Score.add_edge(source, target)

		if(VISUALIZATION):
			print " Writing a GML file for Gephi visualization."
			graphFile = open("score.gml", 'w')
			graphFile.write("graph\n[\n")
			for node in database.keys():
				graphFile.write("  node\n  [\n   id "+node+"\n   label "+node+"\n  ]\n")
			print "\t - Nodes written !"
			for node in database.keys():
				for edgeEnd in database[node]:
					graphFile.write("  edge\n  [\n   source "+node+"\n   target "+edgeEnd+"\n  ]\n")
			print "\t - Edges written !\n"
			graphFile.write("]")

		print " Pickling Score in "+dumpfile+" to save time on next uses."
		filedump = open(dumpfile, 'w')
		pickle.dump([Score, noteCount], filedump)
		filedump.close()

	if ANALYSIS:

		print " Loading Score from pickle."
		filedump = open(dumpfile, 'r')
		(Score, noteCount) = pickle.load(filedump)
		filedump.close()
		print str(len(Score.edges())), noteCount 
		central = []

		print "\n Starting calculation of centrality."

		if(EVALUATE_CENTRALITY):
			results = Queue()
			lock = Lock()
			lockPrint = Lock()

			p1 = Process(target = loadingtime, args=[lockPrint])
			p1.start()
			p2 = Process(target = calcCentrality, args=(Score, results, lock, lockPrint))
			p2.start()
			time.sleep(10)
			lock.acquire(True)
			for i in iter(results.get, 'STOP'):
				central.append(i)
			time.sleep(.1)
			lock.release()
			p1.terminate()
			dumpfile = open("centrality_dump", 'w')
			pickle.dump(central, dumpfile)
			dumpfile.close()
		else:
			dumpfile = open("centrality_dump", 'r')
			central = pickle.load(dumpfile)
			dumpfile.close()

		print "\r\t\t\t\t\t\t\t\t\r\tCentrality values calculated!"

		print "\n Using centrality to establish who had the most influence on the notes.\n"
		winners = [[i for i in sorted(central[2], key=lambda x: central[2][x])][-10:] for j in range (4)]

		influence_scores = {}

		for table in winners:
			for user in table:
				influence_scores[user] = 0
		for table in winners:
			for user in table:
				influence_scores[user] += table.index(user)

		print " Outputting influence list w/ scores. (arbitrary unit)\n"
		leaderboard = [(i, influence_scores[i]) for i in sorted(influence_scores, key=lambda x: influence_scores[x])]
		for score in reversed(leaderboard):
			print " \t"+str(len(leaderboard)-leaderboard.index(score))+" - "+str(score[0])+" - influence: "+str(score[1])