import React, { useEffect, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import { ZoomIn, ZoomOut, Maximize2, RotateCcw, Info, Search, EyeOff } from 'lucide-react'

const ENTITY_COLORS = {
  PERSON: '#4F6B3A',       // Olive
  ORG: '#3E5A7A',          // Slate blue
  ORGANIZATION: '#3E5A7A', // Slate blue
  GPE: '#8A5A83',          // Plum
  LOCATION: '#8A5A83',     // Plum
  PRODUCT: '#B07A2A',      // Ochre
  DATE: '#A3542F',         // Terracotta
  MONEY: '#3F7A72',        // Teal
  DOCUMENT: '#6B6255',     // Umber
  DEFAULT: '#9A8F7E'       // Stone
}

const colorFor = (type) => ENTITY_COLORS[type] || ENTITY_COLORS.DEFAULT

export default function KnowledgeGraph({ graphData, title = "Knowledge Graph" }) {
  const containerRef = useRef(null)
  const cyRef = useRef(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [hiddenTypes, setHiddenTypes] = useState(new Set())
  const [searchQuery, setSearchQuery] = useState('')

  // Build the Cytoscape instance whenever the data changes
  useEffect(() => {
    if (!containerRef.current || !graphData || !graphData.nodes) return

    const elements = [
      ...graphData.nodes.map(n => ({
        data: {
          id: n.id,
          label: n.label || n.text || n.id,
          type: n.type || 'OTHER',
          weight: n.weight || 1,
          degree: n.degree || 0,
          docCount: n.doc_count,
          color: colorFor(n.type)
        }
      })),
      ...(graphData.edges || []).map((e, idx) => ({
        data: {
          id: `edge-${idx}`,
          source: e.source,
          target: e.target,
          label: e.label || 'COOCCURS_WITH',
          weight: e.weight || 1
        }
      }))
    ]

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            'label': 'data(label)',
            'color': '#2B2620',
            'font-size': '11px',
            'font-family': 'IBM Plex Sans, sans-serif',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'text-background-color': '#FBF8F2',
            'text-background-opacity': 0.8,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'width': 'mapData(weight, 1, 10, 24, 48)',
            'height': 'mapData(weight, 1, 10, 24, 48)',
            'border-width': 2,
            'border-color': '#FBF8F2',
            'overlay-opacity': 0
          }
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#2B2620',
            'border-opacity': 1
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 'mapData(weight, 1, 10, 1.5, 4)',
            'line-color': '#C9BDA8',
            'target-arrow-shape': 'none',
            'curve-style': 'bezier',
            'opacity': 0.6
          }
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#A3542F',
            'opacity': 1,
            'width': 3
          }
        },
        // Search: dim what doesn't match (classes, so clearing restores the base styles above)
        { selector: 'node.faded', style: { 'opacity': 0.15 } },
        { selector: 'edge.faded', style: { 'opacity': 0.05 } },
        // Legend filter: hidden entity types (their edges hide with them)
        { selector: 'node.filtered', style: { 'display': 'none' } }
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

    cy.on('tap', 'node', (evt) => {
      const node = evt.target
      cy.elements().removeClass('highlighted')
      node.connectedEdges().addClass('highlighted')

      setSelectedNode({
        id: node.data('id'),
        label: node.data('label'),
        type: node.data('type'),
        color: node.data('color'),
        docCount: node.data('docCount'),
        connections: node.neighborhood('node').length
      })
    })

    // Clicking empty canvas clears the selection
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass('highlighted')
        setSelectedNode(null)
      }
    })

    cyRef.current = cy
    setSelectedNode(null)

    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [graphData])

  // Apply search dimming and type filters; re-runs when the graph is rebuilt too
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return

    const q = searchQuery.trim().toLowerCase()
    cy.batch(() => {
      cy.elements().removeClass('faded filtered')
      cy.nodes().forEach(node => {
        if (hiddenTypes.has(node.data('type'))) node.addClass('filtered')
      })
      if (q) {
        const unmatched = cy.nodes().filter(node => !node.data('label').toLowerCase().includes(q))
        unmatched.addClass('faded')
        unmatched.connectedEdges().addClass('faded')
      }
    })
  }, [searchQuery, hiddenTypes, graphData])

  const toggleType = (type) => {
    setHiddenTypes(prev => {
      const next = new Set(prev)
      next.has(type) ? next.delete(type) : next.add(type)
      return next
    })
    if (selectedNode?.type === type) setSelectedNode(null)
  }

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

  const typeCounts = (graphData?.nodes || []).reduce((acc, n) => {
    const type = n.type || 'OTHER'
    acc[type] = (acc[type] || 0) + 1
    return acc
  }, {})

  const iconButton = 'p-1.5 rounded text-ink-muted hover:text-ink hover:bg-sunken transition-colors'
  const isEmpty = !graphData || !graphData.nodes || graphData.nodes.length === 0

  return (
    <div className="panel relative w-full h-full min-h-[500px] flex flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="px-3 py-2.5 border-b border-line flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-2 min-w-0">
          <span className="text-sm font-medium text-ink truncate">{title}</span>
          <span className="text-xs text-ink-faint shrink-0">
            {graphData?.nodes?.length || 0} entities · {graphData?.edges?.length || 0} links
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-ink-faint absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Find an entity"
              aria-label="Find an entity"
              className="input py-1.5 pl-8 text-xs w-36 sm:w-44"
            />
          </div>

          <div className="flex items-center rounded-md border border-line bg-paper p-0.5">
            <button onClick={handleZoomIn} className={iconButton} title="Zoom in" aria-label="Zoom in">
              <ZoomIn className="w-4 h-4" />
            </button>
            <button onClick={handleZoomOut} className={iconButton} title="Zoom out" aria-label="Zoom out">
              <ZoomOut className="w-4 h-4" />
            </button>
            <button onClick={handleFit} className={iconButton} title="Fit to view" aria-label="Fit to view">
              <Maximize2 className="w-4 h-4" />
            </button>
            <button onClick={handleResetLayout} className={iconButton} title="Rearrange" aria-label="Rearrange layout">
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Legend: click a type to hide or show it */}
      {!isEmpty && (
        <div className="px-3 py-1.5 border-b border-line flex items-center gap-1 overflow-x-auto text-xs text-ink-muted">
          <span className="text-ink-faint shrink-0 mr-1">Show:</span>
          {Object.entries(typeCounts).map(([type, count]) => {
            const hidden = hiddenTypes.has(type)
            return (
              <button
                key={type}
                onClick={() => toggleType(type)}
                aria-pressed={!hidden}
                title={hidden ? `Show ${type}` : `Hide ${type}`}
                className={`flex items-center gap-1.5 shrink-0 px-2 py-0.5 rounded hover:bg-sunken transition-colors ${hidden ? 'text-ink-faint line-through' : ''}`}
              >
                {hidden ? (
                  <EyeOff className="w-3 h-3" />
                ) : (
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colorFor(type) }} />
                )}
                <span>{type} <span className="text-ink-faint">{count}</span></span>
              </button>
            )
          })}
        </div>
      )}

      {/* Cytoscape canvas */}
      <div ref={containerRef} className="flex-1 w-full h-full min-h-[420px] bg-paper" />

      {/* Selected entity */}
      {selectedNode && (
        <div className="absolute bottom-4 left-4 z-20 max-w-xs rounded-md border border-line bg-surface p-3.5 shadow-raised animate-slide-up">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: selectedNode.color }} />
            <span className="text-xs font-medium uppercase tracking-wide text-ink-faint">{selectedNode.type}</span>
          </div>
          <p className="font-serif text-lg font-semibold text-ink leading-snug">{selectedNode.label}</p>
          <p className="mt-1 text-sm text-ink-muted">
            Linked to {selectedNode.connections} other {selectedNode.connections === 1 ? 'entity' : 'entities'}
            {selectedNode.docCount
              ? `, in ${selectedNode.docCount} ${selectedNode.docCount === 1 ? 'document' : 'documents'}`
              : ''}
            .
          </p>
        </div>
      )}

      {isEmpty && (
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none p-6 text-center">
          <Info className="w-6 h-6 text-ink-faint mb-2" />
          <p className="font-medium text-ink">Nothing to show yet</p>
          <p className="mt-1 text-sm text-ink-muted max-w-sm">
            Entities appear here once you upload documents that mention people, organisations, places or dates.
          </p>
        </div>
      )}
    </div>
  )
}
