import React, { useEffect, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import { ZoomIn, ZoomOut, Maximize2, RotateCcw, Filter, Info, Search } from 'lucide-react'

const ENTITY_COLORS = {
  PERSON: '#10B981',       // Emerald
  ORG: '#3B82F6',          // Blue
  ORGANIZATION: '#3B82F6', // Blue
  GPE: '#8B5CF6',          // Purple
  LOCATION: '#8B5CF6',     // Purple
  PRODUCT: '#F59E0B',      // Amber
  DATE: '#EC4899',         // Pink
  MONEY: '#14B8A6',        // Teal
  DOCUMENT: '#06B6D4',     // Cyan
  DEFAULT: '#6B7280'       // Gray
}

export default function KnowledgeGraph({ graphData, title = "Knowledge Graph" }) {
  const containerRef = useRef(null)
  const cyRef = useRef(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [activeFilters, setActiveFilters] = useState(new Set())
  const [searchQuery, setSearchQuery] = useState('')

  // Initialize or update Cytoscape
  useEffect(() => {
    if (!containerRef.current || !graphData || !graphData.nodes) return

    // Transform nodes and edges for Cytoscape
    const elements = [
      ...graphData.nodes.map(n => ({
        data: {
          id: n.id,
          label: n.label || n.text || n.id,
          type: n.type || 'DEFAULT',
          weight: n.weight || 1,
          degree: n.degree || 1,
          color: ENTITY_COLORS[n.type] || ENTITY_COLORS.DEFAULT
        }
      })),
      ...graphData.edges.map((e, idx) => ({
        data: {
          id: `edge-${idx}`,
          source: e.source,
          target: e.target,
          label: e.label || 'COOCCURS_WITH',
          weight: e.weight || 1
        }
      }))
    ]

    // Destroy existing instance
    if (cyRef.current) {
      cyRef.current.destroy()
    }

    // Create Cytoscape instance
    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            'label': 'data(label)',
            'color': '#F3F4F6',
            'font-size': '11px',
            'font-family': 'Plus Jakarta Sans, sans-serif',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'text-background-color': '#111827',
            'text-background-opacity': 0.8,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'width': 'mapData(weight, 1, 10, 24, 48)',
            'height': 'mapData(weight, 1, 10, 24, 48)',
            'border-width': 2,
            'border-color': '#1F2937',
            'overlay-opacity': 0
          }
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#FFFFFF',
            'shadow-blur': 15,
            'shadow-color': 'data(color)',
            'shadow-opacity': 0.8
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 'mapData(weight, 1, 10, 1.5, 4)',
            'line-color': '#374151',
            'target-arrow-color': '#374151',
            'target-arrow-shape': 'none',
            'curve-style': 'bezier',
            'opacity': 0.6
          }
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#60A5FA',
            'opacity': 1,
            'width': 3
          }
        }
      ],
      layout: {
        name: 'cose',
        animate: true,
        animationDuration: 800,
        nodeDimensionsIncludeLabels: true,
        nodeRepulsion: 4500,
        idealEdgeLength: 80,
        edgeElasticity: 0.45,
        gravity: 0.25,
        randomize: false
      }
    })

    // Click handler on nodes
    cy.on('tap', 'node', (evt) => {
      const node = evt.target
      const connectedEdges = node.connectedEdges()
      const connectedNodes = connectedEdges.connectedNodes()

      cy.elements().removeClass('highlighted')
      connectedEdges.addClass('highlighted')

      setSelectedNode({
        id: node.data('id'),
        label: node.data('label'),
        type: node.data('type'),
        color: node.data('color'),
        connections: connectedNodes.length - 1
      })
    })

    // Click canvas clears selection
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass('highlighted')
        setSelectedNode(null)
      }
    })

    cyRef.current = cy

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy()
      }
    }
  }, [graphData])

  // Handle Search Query Filter
  useEffect(() => {
    if (!cyRef.current) return
    const cy = cyRef.current

    if (!searchQuery.trim()) {
      cy.elements().style({ opacity: 1 })
      return
    }

    const q = searchQuery.toLowerCase()
    cy.batch(() => {
      cy.nodes().forEach(node => {
        const matches = node.data('label').toLowerCase().includes(q)
        if (matches) {
          node.style({ opacity: 1 })
          node.connectedEdges().style({ opacity: 0.8 })
        } else {
          node.style({ opacity: 0.15 })
          node.connectedEdges().style({ opacity: 0.05 })
        }
      })
    })
  }, [searchQuery])

  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.3)
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.7)
  const handleFit = () => cyRef.current?.fit(undefined, 40)
  const handleResetLayout = () => {
    cyRef.current?.layout({
      name: 'cose',
      animate: true,
      animationDuration: 600,
      nodeRepulsion: 4500
    }).run()
  }

  const typesPresent = graphData?.nodes 
    ? Array.from(new Set(graphData.nodes.map(n => n.type || 'OTHER')))
    : []

  return (
    <div className="relative w-full h-full min-h-[500px] flex flex-col bg-gray-950/60 rounded-2xl border border-gray-800 overflow-hidden">
      {/* Graph Toolbar */}
      <div className="p-3 bg-gray-900/80 border-b border-gray-800 flex flex-wrap items-center justify-between gap-3 z-10 backdrop-blur">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-bold uppercase tracking-wider text-gray-400">{title}</span>
          <span className="text-xs bg-gray-800 text-gray-300 px-2 py-0.5 rounded-full font-mono">
            {graphData?.nodes?.length || 0} entities • {graphData?.edges?.length || 0} relations
          </span>
        </div>

        {/* Search Input */}
        <div className="flex items-center space-x-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-gray-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search entities..."
              className="bg-gray-950 border border-gray-800 rounded-lg py-1 pl-8 pr-3 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 w-36 sm:w-48"
            />
          </div>

          {/* Canvas Controls */}
          <div className="flex items-center bg-gray-950 rounded-lg border border-gray-800 p-0.5">
            <button
              onClick={handleZoomIn}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded"
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button
              onClick={handleZoomOut}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded"
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <button
              onClick={handleFit}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded"
              title="Fit to Screen"
            >
              <Maximize2 className="w-4 h-4" />
            </button>
            <button
              onClick={handleResetLayout}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded"
              title="Re-layout Graph"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Legend & Types */}
      <div className="px-3 py-1.5 bg-gray-950/40 border-b border-gray-800/60 flex items-center space-x-3 overflow-x-auto text-[11px] text-gray-400">
        <span className="font-semibold text-gray-500 shrink-0">Entity Legend:</span>
        {typesPresent.map(type => (
          <div key={type} className="flex items-center space-x-1.5 shrink-0">
            <span 
              className="w-2.5 h-2.5 rounded-full" 
              style={{ backgroundColor: ENTITY_COLORS[type] || ENTITY_COLORS.DEFAULT }}
            />
            <span>{type}</span>
          </div>
        ))}
      </div>

      {/* Cytoscape Canvas */}
      <div ref={containerRef} className="flex-1 w-full h-full min-h-[420px] bg-[#0A0D14]" />

      {/* Selected Node Drawer */}
      {selectedNode && (
        <div className="absolute bottom-4 left-4 p-4 rounded-xl bg-gray-900/95 border border-gray-700 shadow-2xl backdrop-blur max-w-xs z-20 animate-in fade-in slide-in-from-bottom-2">
          <div className="flex items-center space-x-2 mb-2">
            <span
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: selectedNode.color }}
            />
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400">
              {selectedNode.type}
            </span>
          </div>
          <h4 className="text-base font-bold text-white mb-1">{selectedNode.label}</h4>
          <p className="text-xs text-gray-400">
            Connected to <span className="text-blue-400 font-semibold">{selectedNode.connections}</span> other entities in this document.
          </p>
        </div>
      )}

      {/* Empty State */}
      {(!graphData || !graphData.nodes || graphData.nodes.length === 0) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none p-6 text-center">
          <Info className="w-10 h-10 text-gray-600 mb-2" />
          <h4 className="text-gray-300 font-medium text-sm">No Graph Data Available</h4>
          <p className="text-gray-500 text-xs max-w-sm mt-1">
            Upload documents with entities to generate interactive knowledge graph nodes.
          </p>
        </div>
      )}
    </div>
  )
}
