import networkx
from multiprocessing import Process, Lock, Queue, Value
from multiprocessing.queues import SimpleQueue
import time

def countSteps(p):
	while True:
		time.sleep(0.1)
		p.value+=1
		if p.value%100 == 0:
			print "\t\t\r"+str(p.value),

def degree(G):
	d = 0.0
	for n in len(G.nodes()):
		d += G.degree(G.nodes()[n])
	return d/len(G.nodes())

if __name__ == "__main__":
	Score = networkx.MultiDiGraph()
	for i in range(1,5000):
		e = (i, i+1)
		if e not in Score.edges():
			Score.add_edges_from([e])
	# print Score.edges()

	V = len(Score.nodes())
	E = len(Score.edges())
	D = degree(Score)

	print " Graph - "+str(V)+" : "+str(E)+" : "+str(D)
	time = Value('i', 0)
	p1 = Process(target = countSteps, args=[time])
	p1.start()
	networkx.betweenness_centrality(Score)
	p1.terminate()
	print "Done."

	data = open("banchmark_data", 'a')
	data.write(str(V)+"\t"+str(E)+"\t"+str(D)+"\t"+str(time.value)+"\n")
	data.close()