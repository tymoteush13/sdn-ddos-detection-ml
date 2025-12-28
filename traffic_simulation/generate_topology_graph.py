from graphviz import Graph
from topology_final import MyTopo
from mininet.node import RemoteController

# Topologia
topo = MyTopo()

# Kontroler
controller = RemoteController('c0', ip='127.0.0.1', port=6653)

# Graf
g = Graph('MininetTopology', format='png')
g.attr(label="Topologia sieci SDN zaprojektowana w ramach pracy inżynierskiej", fontsize="18", labelloc="t")

# Kontroler
g.node('c0', shape='box', style='filled', color='lightcoral')

# Switche + hosty
for node in topo.nodes():
    if node.startswith('s'):
        g.node(node, shape='box', style='filled', color='lightblue')
    else:
        g.node(node, shape='ellipse', style='filled', color='lightgrey')

# Normalne połączenia
for src, dst in topo.links(sort=True):
    g.edge(src, dst)

# Połączenia kontrolne (przerywane)
for node in topo.nodes():
    if node.startswith('s'):
        g.edge('c0', node, style='dashed')

# Legenda

# Etykieta "Legenda" jako osobny węzeł
g.node('LegendTitle', label='Legenda:', shape='plaintext', fontsize='20')

# Ikony
g.node('leg_host', label='Host', shape='ellipse', style='filled', color='lightgrey')
g.node('leg_switch', label='Przełącznik OVS', shape='box', style='filled', color='lightblue')
g.node('leg_ctrl', label='Kontroler', shape='box', style='filled', color='lightcoral')

# Zwykłe łącze
g.node('L1', label='', shape='point')
g.node('L2', label='Łącze danych', shape='plaintext')
g.edge('L1', 'L2')

# Połączenie OpenFlow
g.node('O1', label='', shape='point')
g.node('O2', label='OpenFlow 1.3', shape='plaintext')
g.edge('O1', 'O2', style='dashed')

g.body.append('{ rank=sink; LegendTitle; leg_host; leg_switch; leg_ctrl; L1; L2; O1; O2 }')

# Zapis pliku
g.render('topology_graph_polski', cleanup=True)
print("✔ Diagram zapisany jako topology_graph.png z legendą")
