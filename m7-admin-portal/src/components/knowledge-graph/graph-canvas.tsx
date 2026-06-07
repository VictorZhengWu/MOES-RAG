/**
 * D3.js Force-Directed Graph Canvas for Knowledge Graph visualization.
 *
 * WHAT: Renders M4 entities as nodes and relations as edges in an interactive
 *       force-directed layout. Supports drag, zoom, hover tooltips, and click
 *       to inspect entity details.
 *
 * WHY: Replaces the Card-based list view with a visual graph that shows
 *      the structure and relationships in the knowledge graph. Force-directed
 *      layout naturally clusters related entities.
 */

'use client';

import { useEffect, useRef, useCallback } from 'react';

// ---- Types ----

interface GraphNode {
  id: string;
  name: string;
  entity_type: string;
  properties?: Record<string, unknown>;
}

interface GraphEdge {
  source: string;
  target: string;
  relation_type: string;
  confidence?: number;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// ---- Color map per entity type ----

const TYPE_COLORS: Record<string, string> = {
  steel_grade: '#ef4444',
  regulation_clause: '#3b82f6',
  equipment: '#f59e0b',
  system_type: '#8b5cf6',
  parameter: '#10b981',
  ship_type: '#ec4899',
  default: '#6b7280',
};

function nodeColor(type: string): string {
  return TYPE_COLORS[type] || TYPE_COLORS['default'];
}

// ---- Component ----

interface Props {
  data: GraphData | null;
  loading?: boolean;
  onNodeClick?: (node: GraphNode) => void;
}

export function GraphCanvas({ data, loading, onNodeClick }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const renderGraph = useCallback(() => {
    const svg = svgRef.current;
    if (!svg || !data || data.nodes.length === 0) return;

    // Dynamic D3 import (no SSR issues)
    import('d3').then((d3) => {
      const width = svg.clientWidth || 800;
      const height = svg.clientHeight || 600;

      // Clear previous render
      svg.innerHTML = '';

      const simulation = d3.forceSimulation(data.nodes as any)
        .force('link', d3.forceLink(data.edges).id((d: any) => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-200))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30));

      // Edges
      const link = d3.select(svg).append('g')
        .selectAll('line')
        .data(data.edges)
        .join('line')
        .attr('stroke', '#94a3b8')
        .attr('stroke-width', (d: any) => Math.max(1, (d.confidence || 0.5) * 2))
        .attr('stroke-opacity', 0.6);

      // Edge labels
      const edgeLabels = d3.select(svg).append('g')
        .selectAll('text')
        .data(data.edges)
        .join('text')
        .text((d: any) => d.relation_type)
        .attr('font-size', '9px')
        .attr('fill', '#64748b')
        .attr('text-anchor', 'middle');

      // Nodes
      const node = d3.select(svg).append('g')
        .selectAll('g')
        .data(data.nodes)
        .join('g')
        .attr('cursor', 'pointer')
        .call(d3.drag<any, any>()
          .on('start', (event: any, d: any) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event: any, d: any) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event: any, d: any) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }),
        );

      // Node circles
      node.append('circle')
        .attr('r', 8)
        .attr('fill', (d: any) => nodeColor(d.entity_type))
        .attr('stroke', '#fff')
        .attr('stroke-width', 2);

      // Node labels
      node.append('text')
        .text((d: any) => d.name.length > 20 ? d.name.slice(0, 18) + '...' : d.name)
        .attr('dx', 12)
        .attr('dy', 4)
        .attr('font-size', '10px')
        .attr('fill', '#1e293b');

      // Hover tooltip
      node.on('mouseenter', function (event: any, d: any) {
        const tip = tooltipRef.current;
        if (!tip) return;
        tip.style.display = 'block';
        tip.style.left = (event.pageX + 10) + 'px';
        tip.style.top = (event.pageY - 10) + 'px';
        tip.innerHTML = `<strong>${d.name}</strong><br/><span style="color:#64748b">${d.entity_type}</span>`;
      }).on('mouseleave', () => {
        const tip = tooltipRef.current;
        if (tip) tip.style.display = 'none';
      }).on('click', (_event: any, d: any) => {
        onNodeClick?.(d);
      });

      // Simulation tick
      simulation.on('tick', () => {
        link
          .attr('x1', (d: any) => d.source.x)
          .attr('y1', (d: any) => d.source.y)
          .attr('x2', (d: any) => d.target.x)
          .attr('y2', (d: any) => d.target.y);

        edgeLabels
          .attr('x', (d: any) => (d.source.x + d.target.x) / 2)
          .attr('y', (d: any) => (d.source.y + d.target.y) / 2);

        node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
      });
    });
  }, [data, onNodeClick]);

  useEffect(() => {
    renderGraph();
  }, [renderGraph]);

  // Resize observer
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const observer = new ResizeObserver(() => renderGraph());
    observer.observe(svg);
    return () => observer.disconnect();
  }, [renderGraph]);

  // ---- States ----

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[600px] text-sm text-muted-foreground">
        Loading graph data...
      </div>
    );
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-[600px] text-sm text-muted-foreground">
        No graph data available. Parse documents to build the knowledge graph.
      </div>
    );
  }

  return (
    <div className="relative">
      <svg ref={svgRef} className="w-full h-[600px] border rounded-lg bg-white" />
      <div
        ref={tooltipRef}
        className="absolute hidden bg-slate-800 text-white text-xs rounded-lg px-3 py-2 pointer-events-none z-50 shadow-lg"
        style={{ maxWidth: '250px' }}
      />
      <div className="flex gap-3 mt-3 flex-wrap text-xs text-muted-foreground">
        {Object.entries(TYPE_COLORS).filter(([k]) => k !== 'default').map(([type, color]) => (
          <span key={type} className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-full" style={{ background: color }} />
            {type.replace(/_/g, ' ')}
          </span>
        ))}
      </div>
    </div>
  );
}
