"use client"

import { ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Shader,
  Ascii,
  CursorTrail,
  Godrays,
  RadialGradient,
  Tritone
} from 'shaders/react'

export function HeroSection() {
  return (
    <>
      {/* Fixed Shader Background */}
      <div 
        className="fixed inset-0 -z-10"
        aria-hidden="true"
      >
        <Shader className="absolute inset-0">
          <RadialGradient
            center={{ x: 0.83, y: 0.2 }}
            colorA="#030d2b"
            colorB="#010f14"
            colorSpace="oklch"
            radius={1.37} 
          />
          <Ascii
            cellSize={30}
            characters="||||"
            fontFamily="Space Mono"
            spacing={1}
          >
            <Godrays
              backgroundColor="#b59318"
              center={{ x: 0.85, y: 0.15 }}
              density={0.3}
              intensity={0.96}
              rayColor="#fcfeff"
              speed={1}
              spotty={1} 
            />
            <CursorTrail
              colorA="#ffffff"
              colorB="#000000"
              colorSpace="linear"
              length={1}
              radius={0.5}
              shrink={5} />
            <Tritone
              blendMid={0.73}
              colorA="#070b1f"
              colorB="#2600ff"
              colorC="#ffee03"
              colorSpace="oklch"
              visible={true} 
            />
          </Ascii>
        </Shader>
      </div>

      {/* Hero Content */}
      <section className="relative min-h-screen flex flex-col">
        {/* Navigation */}
        <nav className="flex items-center justify-between p-6 md:p-10">
          <div className="flex flex-col gap-1 text-sm tracking-wide">
            <a href="#work" className="text-muted-foreground hover:text-foreground transition-colors">Work</a>
            <a href="#about" className="text-muted-foreground hover:text-foreground transition-colors">About</a>
            <a href="#contact" className="text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1">
              Contact <span className="text-xs">↗</span>
            </a>
          </div>
        </nav>

        {/* Main Hero Content */}
        <div className="flex-1 flex flex-col justify-center px-6 md:px-10 pb-24">
          <div className="max-w-6xl z-10">
            {/* Oversized Typography */}
            <h1 
              className="text-[clamp(3.5rem,12vw,12rem)] font-bold leading-[0.85] tracking-[-0.03em] text-foreground font-[family-name:var(--font-sans)]"
            >
              <span className="block">ANALYZER</span>
              <span className="block">Forensic</span>
              <span className="block text-emerald-500 font-mono tracking-tighter">[FUSION]</span>
            </h1>

            {/* Tagline with accent */}
            <div className="mt-12 md:mt-16 flex flex-col md:flex-row md:items-end gap-8 md:gap-16">
              <p className="text-lg md:text-xl text-muted-foreground max-w-md leading-relaxed">
                Next-generation intelligence platform correlating financial trails and telecom data to uncover hidden networks.
              </p>
              
              <Button 
                variant="outline" 
                size="lg"
                className="group w-fit border-emerald-500/50 hover:border-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-400 transition-all duration-300 bg-black/40 backdrop-blur-md font-mono"
                onClick={() => window.location.href = "/dashboard"}
              >
                INITIALIZE FUSION
                <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Button>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between p-6 md:p-10 border-t border-border/50 bg-black/50 backdrop-blur-md z-10">
          <div className="flex items-center gap-4">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-mono text-sm text-emerald-500/80 tracking-widest">SYSTEM ONLINE</span>
          </div>
          <span className="font-mono text-sm text-muted-foreground">v2.0.0-rc1</span>
        </div>
      </section>
    </>
  )
}
